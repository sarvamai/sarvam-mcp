"""Language identification + text analytics."""

from __future__ import annotations

import json
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import log_tool_error, ready_ctx

LID_PATH = "/text-lid"
ANALYTICS_PATH = "/text-analytics"

# Live-tested 2026-04-27 — these are the only valid `type` values the API accepts.
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
        input: str = Field(description="Text whose language to identify."),
    ) -> dict[str, Any]:
        try:
            sc = await ready_ctx(ctx)
            with measure_tool() as metrics:
                payload, call = await sc.client.post_json(LID_PATH, json_body={"input": input})
                metrics.merge(call)
            return {
                "language_code": payload.get("language_code"),
                "script_code": payload.get("script_code"),
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_identify_language", exc)
            raise

    @mcp.tool(
        name="sarvam_tools_text_analytics",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Run deep analysis on a piece of text by passing a list of typed "
            "questions. Each question needs `id`, `text`, and `type` "
            "(`boolean` | `enum` | `short answer` | `long answer` | `number`). "
            "Returns one answer per question, grounded in the text. Good for "
            "entity extraction, classification, and structured Q&A without "
            "writing prompt boilerplate."
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
        sc = await ready_ctx(ctx)
        # Validate shape upfront — the API's error message is unhelpful.
        valid_types = {"boolean", "enum", "short answer", "long answer", "number"}
        for i, q in enumerate(questions):
            missing = {"id", "text", "type"} - set(q.keys())
            if missing:
                raise ValueError(f"questions[{i}] missing fields: {missing}")
            if q["type"] not in valid_types:
                raise ValueError(
                    f"questions[{i}].type must be one of {sorted(valid_types)}, got {q['type']!r}"
                )

        # Endpoint is multipart, not JSON. `questions` is a JSON-stringified list.
        try:
            with measure_tool() as metrics:
                payload, call = await sc.client.post_multipart(
                    ANALYTICS_PATH,
                    data={"text": text, "questions": json.dumps(questions)},
                )
                metrics.merge(call)
            return {
                "answers": payload.get("answers", []),
                "raw": payload,
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_text_analytics", exc)
            raise
