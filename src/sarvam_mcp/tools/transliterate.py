"""Transliteration — script conversion (Devanagari ↔ Roman, etc.)."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, NumeralsFormat, ready_ctx

TRANSLITERATE_PATH = "/transliterate"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_transliterate",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Convert text between scripts without translating meaning. "
            "Examples: Devanagari → Roman ('नमस्ते' → 'namaste'), Tamil "
            "script → Latin, etc. Use `spoken_form=True` to expand digits "
            "and abbreviations into spoken form."
        ),
    )
    async def sarvam_transliterate(
        ctx: Context,
        input: str = Field(description="Text to transliterate."),
        source_language_code: LanguageCode = Field(
            description="Source language code (e.g. 'hi-IN'), or 'auto' to auto-detect.",
        ),
        target_language_code: LanguageCode = Field(
            description="Target language code (script of the output).",
        ),
        numerals_format: NumeralsFormat = Field(default="international"),
        spoken_form: bool = Field(
            default=False,
            description="Expand numbers/abbreviations into spoken form.",
        ),
        spoken_form_numerals_language: LanguageCode | None = Field(
            default=None,
            description="Language to use when speaking out numbers (only with spoken_form=True).",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        # Upstream /transliterate accepts "auto", not "unknown".
        src = "auto" if source_language_code == "unknown" else source_language_code
        body: dict[str, Any] = {
            "input": input,
            "source_language_code": src,
            "target_language_code": target_language_code,
            "numerals_format": numerals_format,
            "spoken_form": spoken_form,
        }
        if spoken_form_numerals_language:
            body["spoken_form_numerals_language"] = spoken_form_numerals_language

        with measure_tool() as metrics:
            payload, call = await sc.client.post_json(TRANSLITERATE_PATH, json_body=body)
            metrics.merge(call)

        return {
            "transliterated_text": payload.get("transliterated_text", ""),
            "source_language_code": payload.get("source_language_code"),
            "observability": metrics.to_response_block(),
        }
