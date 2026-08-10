"""``sv_dub`` — audio in → translated audio out.

The flagship "wow" demo: take an Indic-language audio file, transcribe it,
translate the transcript to a target Indic language, and re-synthesize.
ElevenLabs has Dubbing as a separate paid product; here it's one MCP call.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import (
    BulbulSpeaker,
    LanguageCode,
    TtsLanguageCode,
    log_tool_error,
    ready_ctx,
    resolve_file_input,
)
from sarvam_mcp.workflows._helpers import (
    stt_transcribe,
    translate_text,
    tts_synthesize,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_dub",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Dub an Indic audio file into another Indic language. Pipeline: "
            "STT → Mayura or Sarvam-Translate → TTS. Returns the "
            "original transcript, translated transcript, and a path to the "
            "newly-dubbed WAV file."
        ),
    )
    async def sv_dub(
        ctx: Context,
        target_language_code: TtsLanguageCode = Field(
            description="Output language for the dubbed audio.",
        ),
        audio_path: str | None = Field(default=None, description="Local path to the source audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio data."),
        audio_url: str | None = Field(default=None, description="URL to fetch the audio file from."),
        filename: str | None = Field(default=None, description="Filename with extension (for base64/URL)."),
        source_language_code: LanguageCode = Field(
            default="unknown",
            description="STT language hint. 'unknown' enables auto-detect.",
        ),
        speaker: BulbulSpeaker = Field(default="priya"),
        translate_model: str = Field(
            default="mayura:v1",
            description="`mayura:v1` (11 langs, modes) or `sarvam-translate:v1` (22 langs).",
        ),
        translate_mode: str = Field(default="formal"),
    ) -> dict[str, Any]:
        try:
            return await _sv_dub_impl(
                ctx, target_language_code, audio_path, audio_base64, audio_url,
                filename, source_language_code, speaker, translate_model, translate_mode,
            )
        except Exception as exc:
            log_tool_error("sarvam_tools_dub", exc)
            raise

    async def _sv_dub_impl(
        ctx, target_language_code, audio_path, audio_base64, audio_url,
        filename, source_language_code, speaker, translate_model, translate_mode,
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                await ctx.info("Transcribing source audio…")
                transcript, detected_lang = await stt_transcribe(
                    sc, path, language_code=source_language_code, metrics=metrics
                )
                if not transcript.strip():
                    raise RuntimeError("STT returned an empty transcript — nothing to dub.")

                source_lang = detected_lang or (
                    source_language_code if source_language_code != "unknown" else "hi-IN"
                )

                await ctx.info(
                    f"Translating from {source_lang} to {target_language_code}…"
                )
                translated = await translate_text(
                    sc,
                    transcript,
                    source_language_code=source_lang,
                    target_language_code=target_language_code,
                    model=translate_model,
                    mode=translate_mode,
                    metrics=metrics,
                )
                if not translated.strip():
                    raise RuntimeError("Translate returned empty text.")

                await ctx.info("Synthesizing dubbed audio…")
                stored = await tts_synthesize(
                    sc,
                    translated,
                    target_language_code=target_language_code,
                    speaker=speaker,
                    filename_prefix="sv-dub",
                    metrics=metrics,
                )

        return {
            "source_transcript": transcript,
            "source_language": source_lang,
            "translated_transcript": translated,
            "target_language": target_language_code,
            "audio_file_path": stored.file_path,
            "audio_resource_uri": stored.resource_uri,
            "audio_size_bytes": stored.size_bytes,
            "observability": metrics.to_response_block(),
        }
