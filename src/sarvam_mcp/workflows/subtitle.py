from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import (
    LanguageCode,
    ready_ctx,
    resolve_file_input,
)
from sarvam_mcp.workflows._helpers import (
    stt_transcribe_with_timestamps,
    translate_text,
)


def _format_timestamp(seconds: float, fmt: Literal["srt", "vtt"] = "srt") -> str:
    """Format seconds into SRT (00:00:01,500) or WebVTT (00:00:01.500) format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))

    if millis >= 1000:
        secs += 1
        millis = 0

    sep = "," if fmt == "srt" else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def _build_subtitle_blocks(
    timestamps: list[dict[str, Any]],
    fmt: Literal["srt", "vtt"] = "srt",
    max_words_per_block: int = 8,
    max_duration_seconds: float = 5.0,
) -> str:
    """Group timestamped word items into subtitle blocks."""
    if not timestamps:
        return ""

    blocks: list[str] = []

    if fmt == "vtt":
        blocks.append("WEBVTT\n")

    current_words: list[str] = []
    block_start: float | None = None
    block_end: float = 0.0
    index = 1

    for item in timestamps:
        word = item.get("word") or item.get("text") or ""
        start = float(item.get("start_time_seconds") or item.get("start") or 0.0)
        end = float(item.get("end_time_seconds") or item.get("end") or 0.0)

        if block_start is None:
            block_start = start

        current_words.append(word)
        block_end = end

        # Flush block if max words or max duration exceeded
        if len(current_words) >= max_words_per_block or (block_end - block_start) >= max_duration_seconds:
            text = " ".join(current_words)
            t1 = _format_timestamp(block_start, fmt)
            t2 = _format_timestamp(block_end, fmt)
            blocks.append(f"{index}\n{t1} --> {t2}\n{text}\n")
            index += 1
            current_words = []
            block_start = None

    if current_words and block_start is not None:
        text = " ".join(current_words)
        t1 = _format_timestamp(block_start, fmt)
        t2 = _format_timestamp(block_end, fmt)
        blocks.append(f"{index}\n{t1} --> {t2}\n{text}\n")

    return "\n".join(blocks)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_subtitles",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Generate an SRT or WebVTT subtitle file from an Indic audio file. "
            "Pipeline: STT (with timestamps) → optional Translation → Subtitle Formatter (.srt / .vtt).\n\n"
            "Returns the formatted subtitle content and path to the output subtitle file."
        ),
    )
    async def sv_subtitles(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to audio file."),
        audio_base64: str | None = Field(default=None, description="Base64 encoded audio string."),
        audio_url: str | None = Field(default=None, description="URL of the audio file."),
        filename: str | None = Field(default=None, description="Filename with extension."),
        language_code: LanguageCode = Field(
            default="unknown", description="Audio language code (e.g. 'hi-IN'). Use 'unknown' to auto-detect."
        ),
        target_language_code: LanguageCode | None = Field(
            default=None,
            description="Optional target language code to translate subtitles to (e.g. 'en-IN').",
        ),
        format: Literal["srt", "vtt"] = Field(
            default="srt", description="Subtitle output format: 'srt' (default) or 'vtt'."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64, file_url=audio_url, filename=filename
        ) as path:
            with measure_tool() as metrics:
                await ctx.info(f"Transcribing {path.name} with timestamps…")
                transcript, detected_lang, timestamps = await stt_transcribe_with_timestamps(
                    sc, path, language_code=language_code, metrics=metrics
                )

                if not transcript.strip() or not timestamps:
                    raise RuntimeError("STT returned empty transcript or no timestamps")

                source_lang = detected_lang or (language_code if language_code != "unknown" else "hi-IN")

                # Build original subtitle content
                subtitle_content = _build_subtitle_blocks(timestamps, fmt=format)

                # Optional translation
                translated_content = None
                if target_language_code and target_language_code != source_lang:
                    await ctx.info(f"Translating subtitles to {target_language_code}…")
                    translated_text = await translate_text(
                        sc,
                        transcript,
                        source_language_code=source_lang,
                        target_language_code=target_language_code,
                        metrics=metrics,
                    )
                    translated_content = translated_text

                # Save subtitle file to disk
                ext = f".{format}"
                out_name = f"{path.stem}{ext}"
                out_path = path.parent / out_name
                out_path.write_text(subtitle_content, encoding="utf-8")

        return {
            "transcript": transcript,
            "source_language_code": source_lang,
            "target_language_code": target_language_code,
            "format": format,
            "subtitle_content": subtitle_content,
            "translated_content": translated_content,
            "subtitle_file_path": str(out_path),
            "observability": metrics.to_response_block(),
        }
