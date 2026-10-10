"""``sarvam_tools_meet`` — Meeting transcription and summarization for Indic-language audio.

Audio in → STT with diarization → LLM → summary, action items, decisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, SarvamLLM, ready_ctx, resolve_file_input
from sarvam_mcp.workflows._helpers import _audio_mime, llm_complete


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_meet",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Transcribe an Indic-language meeting audio file with speaker diarization, then extract "
            "a summary, action items, and decisions using Sarvam LLM. "
            "Returns a structured JSON response with the full transcript and meeting analysis."
        ),
    )
    async def sarvam_tools_meet(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio."),
        audio_url: str | None = Field(default=None, description="URL to audio file."),
        filename: str | None = Field(
            default=None, description="Filename with extension for base64/URL input."
        ),
        language_code: LanguageCode = Field(
            default="unknown", description="BCP-47 language code. 'unknown' auto-detects."
        ),
        llm_model: SarvamLLM = Field(default="sarvam-105b"),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path,
            file_base64=audio_base64,
            file_url=audio_url,
            filename=filename,
        ) as audio_file:
            with measure_tool() as metrics:
                await ctx.info(f"Transcribing {audio_file.name} with diarization…")
                stt_body, stt_call = await _stt_diarized(sc, audio_file, language_code=language_code)
                metrics.merge(stt_call)

                transcript: str = stt_body.get("transcript", "")
                diarized_transcript: list | None = stt_body.get("diarized_transcript")
                detected_language: str | None = stt_body.get("language_code")

                await ctx.info("Analyzing meeting transcript with LLM…")
                raw_analysis = await llm_complete(
                    sc,
                    [
                        {
                            "role": "system",
                            "content": (
                                "You are an AI assistant that analyzes meeting transcripts. "
                                "Return ONLY a JSON object with keys: summary (string), "
                                "action_items (list of strings), decisions (list of strings)."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Meeting transcript:\n{transcript}\n\n"
                                "Extract: a 2-3 sentence summary, a list of action items "
                                "(who does what), and a list of decisions made."
                            ),
                        },
                    ],
                    model=llm_model,
                    temperature=0.2,
                    max_tokens=800,
                    metrics=metrics,
                )

        summary, action_items, decisions = _parse_llm_response(raw_analysis)

        return {
            "transcript": transcript,
            "diarized_transcript": diarized_transcript,
            "language_code": detected_language,
            "summary": summary,
            "action_items": action_items,
            "decisions": decisions,
            "observability": metrics.to_response_block(),
        }


async def _stt_diarized(
    sc: ServerContext,
    audio_path: Path,
    *,
    language_code: str = "unknown",
    model: str = "saaras:v4",
) -> tuple[dict[str, Any], Any]:
    with audio_path.open("rb") as fh:
        files = {"file": (audio_path.name, fh, _audio_mime(audio_path))}
        data: dict[str, Any] = {
            "model": model,
            "language_code": language_code,
            "with_timestamps": "false",
            "with_diarization": "true",
        }
        body, call = await sc.client.post_multipart("/speech-to-text", data=data, files=files)
    return body, call


def _parse_llm_response(raw: str) -> tuple[str, list[str], list[str]]:
    try:
        parsed = json.loads(raw)
        summary = parsed.get("summary", raw)
        action_items = parsed.get("action_items", [])
        decisions = parsed.get("decisions", [])
        return summary, action_items, decisions
    except (json.JSONDecodeError, AttributeError):
        return raw, [], []
