"""Language identification + text analytics."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import ready_ctx

LID_PATH = "/text-lid"

# Kept for reference only — /text-analytics was permanently removed by Sarvam.
QuestionType = Literal["boolean", "enum", "short answer", "long answer", "number"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_identify_language",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Detect the language and script of input text. Returns BCP-47 "
            "language code (e.g. 'hi-IN') and script code (e.g. 'Devanagari'). "
            "Useful as a pre-step before TTS or translate to pick the right "
            "language args automatically."
        ),
    )
    async def sarvam_identify_language(
        ctx: Context,
        input: str = Field(description="Text whose language to identify. Max 1000 characters."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.post_json(LID_PATH, json_body={"input": input})
            metrics.merge(call)
        return {
            "language_code": payload.get("language_code"),
            "script_code": payload.get("script_code"),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_text_analytics",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "PERMANENTLY REMOVED: Sarvam retired the old analytics/parse API family "
            "(this `/text-analytics` endpoint included) — confirmed via a direct API "
            "call outside this tool (404, first observed 2026-08-13) and via Sarvam's "
            "own SDK release notes, which describe the removal as deliberate, not an "
            "outage. Calling this tool raises immediately instead of making a doomed "
            "network round trip. There is no direct 1:1 replacement for typed-question "
            "text analysis; for document/text extraction, check whether "
            "'SarvamParse' (a new lightweight beta endpoint) fits your use case — "
            "see docs.sarvam.ai for current availability and request shape."
        ),
    )
    async def sarvam_text_analytics(
        ctx: Context,
        text: str = Field(description="Text to analyze."),
        questions: list[dict[str, Any]] = Field(
            description=(
                "List of question objects: "
                "[{'id': 'q1', 'text': 'When was X founded?', 'type': 'short answer'}, ...]. "
                "Required fields: id (str), text (str), type (one of "
                "'boolean'|'enum'|'short answer'|'long answer'|'number'). "
                "For 'enum' questions, also include 'options': ['a', 'b', ...]."
            ),
        ),
    ) -> dict[str, Any]:
        raise RuntimeError(
            "/text-analytics was permanently removed by Sarvam (not a transient "
            "outage) — this tool no longer attempts the call. See "
            "docs.sarvam.ai for 'SarvamParse' (beta), which may cover your use case, "
            "or dashboard.sarvam.ai for current API availability."
        )
