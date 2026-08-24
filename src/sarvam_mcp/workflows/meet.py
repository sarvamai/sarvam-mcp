"""``sv_meet`` — meeting transcription, diarization, and summarisation.

Pipeline: batch STT with diarization → speaker-labelled transcript →
LLM structured summary (meeting overview, action items, decisions).
"""

from __future__ import annotations

import re
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, SarvamLLM, ready_ctx, resolve_file_input
from sarvam_mcp.workflows._helpers import llm_complete, stt_transcribe_diarized

_SYSTEM_PROMPT = """\
You are a meeting summariser. You will be given a speaker-labelled transcript of a meeting.
Respond ONLY in the exact format below, with no additional text before or after.

## Summary
<2-4 sentence overview of what the meeting was about>

## Action Items
- <action item with owner if mentioned>
- <next action item>

## Decisions
- <decision reached>
- <next decision>

If there are no action items or no decisions, write "None." as the sole item under that heading.\
"""


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_meet",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Transcribe a meeting recording and produce a structured summary. "
            "Pipeline: batch STT with speaker diarization → speaker-labelled transcript → "
            "LLM extraction of summary, action items, and decisions. "
            "Works with long audio files; supports all Indic languages."
        ),
    )
    async def sv_meet(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to the meeting audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio data."),
        audio_url: str | None = Field(default=None, description="URL to fetch the audio file from."),
        filename: str | None = Field(default=None, description="Filename with extension (for base64/URL)."),
        language_code: LanguageCode = Field(
            default="unknown",
            description="STT language hint. 'unknown' enables auto-detect.",
        ),
        num_speakers: int | None = Field(
            default=None,
            description="Expected number of speakers. Improves diarization accuracy when known.",
            ge=2,
            le=10,
        ),
        llm_model: SarvamLLM = Field(
            default="sarvam-30b",
            description="`sarvam-30b` (default) or `sarvam-105b` (flagship).",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path,
            file_base64=audio_base64,
            file_url=audio_url,
            filename=filename,
        ) as path:
            with measure_tool() as metrics:
                await ctx.info("Transcribing meeting audio with diarization…")
                flat_transcript, diarized_turns, detected_lang = await stt_transcribe_diarized(
                    sc,
                    path,
                    language_code=language_code,
                    num_speakers=num_speakers,
                    metrics=metrics,
                    ctx=ctx,
                )

                if not flat_transcript.strip() and not diarized_turns:
                    raise RuntimeError("STT returned an empty transcript — nothing to summarise.")

                labeled_transcript, normalized_turns = _render_transcript(diarized_turns, flat_transcript)

                await ctx.info("Summarising meeting with LLM…")
                raw_llm = await llm_complete(
                    sc,
                    [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": f"TRANSCRIPT:\n{labeled_transcript}"},
                    ],
                    model=llm_model,
                    temperature=0.3,
                    max_tokens=1200,
                    metrics=metrics,
                )

        summary, action_items, decisions = _parse_llm_sections(raw_llm)

        return {
            "transcript": labeled_transcript,
            "diarized_turns": normalized_turns,
            "language_code": detected_lang,
            "summary": summary,
            "action_items": action_items,
            "decisions": decisions,
            "observability": metrics.to_response_block(),
        }


# ----- helpers ---------------------------------------------------------------


def _render_transcript(
    diarized_turns: list[dict[str, Any]],
    flat_fallback: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Build a labelled transcript string and normalised turn list.

    Maps SPEAKER_00 → Speaker 1, SPEAKER_01 → Speaker 2, etc.
    Falls back to the flat STT transcript when no diarized turns are available.
    """
    if not diarized_turns:
        return flat_fallback, []

    speaker_map: dict[str, str] = {}
    normalized: list[dict[str, Any]] = []
    lines: list[str] = []

    for turn in diarized_turns:
        raw_id = str(turn.get("speaker", "SPEAKER_00"))
        if raw_id not in speaker_map:
            speaker_map[raw_id] = f"Speaker {len(speaker_map) + 1}"
        label = speaker_map[raw_id]
        text = (turn.get("transcript") or turn.get("text") or "").strip()
        normalized.append(
            {
                "speaker": label,
                "text": text,
                "start": turn.get("start"),
                "end": turn.get("end"),
            }
        )
        if text:
            lines.append(f"{label}: {text}")

    return "\n".join(lines), normalized


def _parse_llm_sections(text: str) -> tuple[str, list[str], list[str]]:
    """Split LLM output into (summary, action_items, decisions)."""
    summary = ""
    action_items: list[str] = []
    decisions: list[str] = []

    for section in re.split(r"^##\s+", text, flags=re.MULTILINE):
        section = section.strip()
        if not section:
            continue
        lines = section.splitlines()
        header = lines[0].strip().lower()
        body = "\n".join(lines[1:]).strip()

        if "summary" in header:
            summary = body
        elif "action" in header:
            action_items = _extract_bullets(body)
        elif "decision" in header:
            decisions = _extract_bullets(body)

    return summary, action_items, decisions


def _extract_bullets(text: str) -> list[str]:
    """Parse bullet list lines into plain strings. Skips 'None.' placeholders."""
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            content = line[2:].strip()
        elif line[0].isdigit() and ". " in line:
            content = line.split(". ", 1)[1].strip()
        else:
            continue
        if content.lower() not in {"none.", "none"}:
            items.append(content)
    return items
