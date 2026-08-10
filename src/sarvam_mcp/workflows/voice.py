"""``sv_voice`` — full voice loop in a single tool call.

Audio in → STT → LLM reply → TTS audio out. Effectively a turnkey
voice agent reachable from any MCP client.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import (
    BulbulSpeaker,
    LanguageCode,
    SarvamLLM,
    TtsLanguageCode,
    log_tool_error,
    ready_ctx,
    resolve_file_input,
)
from sarvam_mcp.workflows._helpers import (
    llm_complete,
    stt_transcribe,
    tts_synthesize,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_voice",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "End-to-end voice agent loop: transcribe an Indic audio file, "
            "send the transcript to the Indic-tuned LLM for a reply, then "
            "synthesize the reply to audio.\n\n"
            "Returns: transcript, reply text, output audio file path. "
            "Default reply language follows the detected input language; "
            "set `reply_language` to force a specific output."
        ),
    )
    async def sv_voice(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to the input audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio data."),
        audio_url: str | None = Field(default=None, description="URL to fetch the audio file from."),
        filename: str | None = Field(default=None, description="Filename with extension (for base64/URL)."),
        system_prompt: str = Field(
            default=(
                "You are a concise, helpful assistant fluent in Indic languages. "
                "Reply in the user's input language unless asked otherwise."
            ),
            description="System message guiding the LLM reply.",
        ),
        input_language: LanguageCode = Field(
            default="unknown",
            description="STT hint. 'unknown' enables language auto-detect.",
        ),
        reply_language: TtsLanguageCode | None = Field(
            default=None,
            description=(
                "Force the TTS output language. Defaults to the detected "
                "input language (or hi-IN if detection fails)."
            ),
        ),
        speaker: BulbulSpeaker = Field(default="priya"),
        llm_model: SarvamLLM = Field(
            default="sarvam-105b",
            description="`sarvam-105b` (flagship, the only current chat model).",
        ),
    ) -> dict[str, Any]:
        try:
            return await _sv_voice_impl(
                ctx, audio_path, audio_base64, audio_url, filename,
                system_prompt, input_language, reply_language, speaker, llm_model,
            )
        except Exception as exc:
            log_tool_error("sarvam_tools_voice", exc)
            raise

    async def _sv_voice_impl(
        ctx, audio_path, audio_base64, audio_url, filename,
        system_prompt, input_language, reply_language, speaker, llm_model,
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                await ctx.info("Transcribing input audio…")
                transcript, detected_lang = await stt_transcribe(
                    sc, path, language_code=input_language, metrics=metrics
                )
                if not transcript.strip():
                    raise RuntimeError("STT returned an empty transcript — nothing to reply to.")

                target_tts_lang = reply_language or _coerce_tts_language(detected_lang)

                await ctx.info("Generating LLM reply…")
                reply_text = await llm_complete(
                    sc,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": transcript},
                    ],
                    model=llm_model,
                    metrics=metrics,
                )
                if not reply_text:
                    raise RuntimeError("LLM returned an empty reply.")

                await ctx.info("Synthesizing reply audio…")
                stored = await tts_synthesize(
                    sc,
                    reply_text,
                    target_language_code=target_tts_lang,
                    speaker=speaker,
                    filename_prefix="sv-voice",
                    metrics=metrics,
                )

        return {
            "transcript": transcript,
            "detected_language": detected_lang,
            "reply_text": reply_text,
            "reply_language": target_tts_lang,
            "audio_file_path": stored.file_path,
            "audio_resource_uri": stored.resource_uri,
            "audio_size_bytes": stored.size_bytes,
            "observability": metrics.to_response_block(),
        }


# ----- helpers -------------------------------------------------------------

# TTS covers these 11 languages. Anything else falls back to hi-IN.
_TTS_SUPPORTED = {
    "en-IN", "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN",
    "kn-IN", "ml-IN", "mr-IN", "pa-IN", "od-IN",
}


def _coerce_tts_language(detected: str | None) -> TtsLanguageCode:
    if detected and detected in _TTS_SUPPORTED:
        return detected  # type: ignore[return-value]
    return "hi-IN"
