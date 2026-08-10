"""Text translation — Mayura (11 langs) and Sarvam-Translate (23 langs)."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import (
    LanguageCode,
    NumeralsFormat,
    OutputScript,
    SpeakerGender,
    TranslateMode,
    log_tool_error,
    ready_ctx,
)

TRANSLATE_PATH = "/translate"

# Picks Mayura (11 langs, modes) vs Sarvam-Translate v1 (23 langs, formal only).
TranslateModel = Literal["mayura:v1", "sarvam-translate:v1"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_translate",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Translate text between English and Indian languages.\n\n"
            "Two backing models:\n"
            "- `mayura:v1` — 11 languages, supports formal / colloquial / "
            "code-mixed modes, script + numeral controls. Best for short, "
            "stylized translations.\n"
            "- `sarvam-translate:v1` — all 22 scheduled languages + English, "
            "formal only. Best when you need broad coverage."
        ),
    )
    async def sarvam_translate(
        ctx: Context,
        input: str = Field(description="Text to translate (max ~2000 chars)."),
        source_language_code: LanguageCode = Field(
            description="Source BCP-47 code, or 'auto' to auto-detect.",
        ),
        target_language_code: LanguageCode = Field(description="Target BCP-47 code."),
        model: TranslateModel = Field(
            default="mayura:v1",
            description="Pick `sarvam-translate:v1` for the 22-language set.",
        ),
        mode: TranslateMode = Field(
            default="formal",
            description="Mayura only. Ignored by sarvam-translate:v1.",
        ),
        output_script: OutputScript | None = Field(
            default=None,
            description="Mayura only. None = native script.",
        ),
        numerals_format: NumeralsFormat = Field(default="international"),
        speaker_gender: SpeakerGender | None = Field(
            default=None,
            description="Helps disambiguate gendered languages (e.g. Hindi).",
        ),
        enable_preprocessing: bool = Field(default=True),
    ) -> dict[str, Any]:
        try:
            sc = await ready_ctx(ctx)
            src = "auto" if source_language_code == "unknown" else source_language_code
            body: dict[str, Any] = {
                "input": input,
                "source_language_code": src,
                "target_language_code": target_language_code,
                "model": model,
                "numerals_format": numerals_format,
                "enable_preprocessing": enable_preprocessing,
            }
            if model == "mayura:v1":
                body["mode"] = mode
                if output_script:
                    body["output_script"] = output_script
            if speaker_gender:
                body["speaker_gender"] = speaker_gender

            with measure_tool() as metrics:
                payload, call = await sc.client.post_json(TRANSLATE_PATH, json_body=body)
                metrics.merge(call)

            return {
                "translated_text": payload.get("translated_text", ""),
                "source_language_code": payload.get("source_language_code"),
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_translate", exc)
            raise
