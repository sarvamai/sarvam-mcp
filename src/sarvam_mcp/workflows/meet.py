"""``sv_meet`` — meeting transcription, diarization, and summarisation.

Batch-transcribes a long audio recording with speaker diarization, then asks
the LLM to turn the speaker-labelled transcript into a summary, action items,
and decisions. Composes ``stt_batch_transcribe`` (tools/stt.py) and
``llm_complete`` (workflows/_helpers.py) — no new API dependency.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, SarvamLLM, ready_ctx, resolve_file_input
from sarvam_mcp.tools.stt import stt_batch_transcribe
from sarvam_mcp.workflows._helpers import llm_complete

_SYSTEM_PROMPT = (
    "You produce structured meeting minutes from a speaker-labelled transcript. "
    "Reply with ONLY a JSON object — no prose, no markdown code fences — matching "
    'exactly this shape: {"summary": str, "action_items": [str], "decisions": [str]}. '
    "summary is a short paragraph. action_items are concrete follow-ups, phrased as "
    "tasks. decisions are choices the group settled on. Use an empty list if there are none."
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_meet",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Meeting transcription workflow: batch-transcribes a long audio recording "
            "with speaker diarization, then asks the LLM for a summary, action items, "
            "and decisions.\n\n"
            "Returns: speaker-labelled transcript, raw diarized turns, summary, "
            "action items, decisions. For files under ~30s or when diarization "
            "isn't needed, use sarvam_tools_stt_transcribe instead."
        ),
    )
    async def sv_meet(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to the input audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio data."),
        audio_url: str | None = Field(default=None, description="URL to fetch the audio file from."),
        filename: str | None = Field(default=None, description="Filename with extension (for base64/URL)."),
        language_code: LanguageCode = Field(
            default="unknown",
            description="STT hint. 'unknown' enables language auto-detect.",
        ),
        num_speakers: int | None = Field(
            default=None,
            description="Hint for diarization: expected number of speakers.",
        ),
        llm_model: SarvamLLM = Field(
            default="sarvam-30b",
            description="`sarvam-30b` (default) or `sarvam-105b` (flagship).",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                await ctx.info("Transcribing meeting audio with diarization…")
                batch_result = await stt_batch_transcribe(
                    sc,
                    ctx,
                    path,
                    language_code=language_code,
                    with_diarization=True,
                    num_speakers=num_speakers,
                    metrics=metrics,
                )

                if "error" in batch_result:
                    return {**batch_result, "observability": metrics.to_response_block()}

                transcript_text, turns = _render_diarized_transcript(
                    batch_result.get("diarized_transcript"),
                    batch_result.get("transcript", ""),
                )
                if not transcript_text.strip():
                    raise RuntimeError(
                        "Batch STT completed but returned an empty transcript — nothing to summarize."
                    )

                await ctx.info("Summarizing transcript…")
                llm_reply = await llm_complete(
                    sc,
                    [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": transcript_text},
                    ],
                    model=llm_model,
                    temperature=0.1,
                    max_tokens=1200,
                    metrics=metrics,
                )
                parsed = _parse_meeting_summary(llm_reply)

        return {
            "job_id": batch_result.get("job_id"),
            "job_state": batch_result.get("job_state"),
            "transcript": transcript_text,
            "diarized_turns": turns,
            "language_code": batch_result.get("language_code"),
            **parsed,
            "observability": metrics.to_response_block(),
        }


def _render_diarized_transcript(
    diarized_transcript: dict[str, Any] | None,
    fallback_transcript: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Render diarized entries into a speaker-labelled transcript string.

    ``diarized_transcript`` is ``{"entries": [{"transcript", "start_time_seconds",
    "end_time_seconds", "speaker_id"}, ...]}`` per the Sarvam batch STT API.
    Falls back to the plain transcript, unlabelled, when diarization isn't
    present — it isn't guaranteed even with ``with_diarization=True`` (e.g.
    very short or single-speaker audio).
    """
    entries = (diarized_transcript or {}).get("entries") or []
    if not entries:
        return fallback_transcript, []

    lines: list[str] = []
    for entry in entries:
        speaker = f"Speaker {entry.get('speaker_id', '?')}"
        text = entry.get("transcript", "")
        start = entry.get("start_time_seconds")
        end = entry.get("end_time_seconds")
        if start is not None and end is not None:
            lines.append(f"[{start:.1f}s–{end:.1f}s] {speaker}: {text}")
        else:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines), entries


def _parse_meeting_summary(raw: str) -> dict[str, Any]:
    """Parse the LLM's JSON reply into summary/action_items/decisions.

    Strips a leading/trailing markdown code fence if present (models often
    add one despite instructions not to), then ``json.loads()``. Degrades to
    a ``parse_warning`` shape on any failure — including valid-but-non-dict
    JSON — rather than silently returning empty lists as if they were real
    output.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if not isinstance(parsed, dict):
        return {
            "summary": raw,
            "action_items": [],
            "decisions": [],
            "parse_warning": "LLM did not return a valid JSON object; summary is the raw model output.",
        }

    return {
        "summary": parsed.get("summary", raw),
        "action_items": parsed.get("action_items") or [],
        "decisions": parsed.get("decisions") or [],
    }
