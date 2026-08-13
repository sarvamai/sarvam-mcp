"""``sarvam_code_*`` documentation tools.

Four tools exposed:
  - sarvam_code_api_reference  — endpoint shapes (params, response, gotchas)
  - sarvam_code_languages      — supported language codes per API
  - sarvam_code_speakers       — TTS speakers per model tag
  - sarvam_code_pricing        — current pricing structure

Source-of-truth data lives in ``code/_data.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.code import _data

# ---- Type literals -------------------------------------------------------

ApiName = Literal[
    "stt", "stt_translate", "tts", "translate", "transliterate",
    "lid", "llm", "vision",
]
EndpointPath = Literal[
    "/speech-to-text",
    "/speech-to-text-translate",
    "/speech-to-text/job/init",
    "/text-to-speech",
    "/translate",
    "/transliterate",
    "/text-lid",
    "/text-analytics",
    "/v1/chat/completions",
    "/doc-digitization/job/v1",
    "/text-to-speech/pronunciation-dictionary",
    "/text-to-speech/ws",
]
TtsModel = Literal["bulbul:v3"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_code_api_reference",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Return the authoritative request/response shape for a Sarvam "
            "API endpoint — parameters, defaults, content type, auth header, "
            "common gotchas. Faster + more accurate than free-text doc "
            "search when the agent already knows which endpoint to use."
        ),
    )
    async def sarvam_code_api_reference(
        ctx: Context,
        endpoint: EndpointPath = Field(description="The Sarvam API path, e.g. '/text-to-speech'."),
    ) -> dict[str, Any]:
        ref = _data.API_REFERENCE.get(endpoint)
        if not ref:
            return {
                "endpoint": endpoint,
                "found": False,
                "note": "Unknown endpoint. Available: " + ", ".join(sorted(_data.API_REFERENCE.keys())),
            }
        return {
            "endpoint": endpoint,
            "found": True,
            **ref,
        }

    @mcp.tool(
        name="sarvam_code_languages",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "List supported BCP-47 language codes for a given Sarvam API. "
            "Critical because coverage varies by API: STT supports 23 langs, "
            "TTS supports 11, etc. Returns code + display name + script."
        ),
    )
    async def sarvam_code_languages(
        ctx: Context,
        api: ApiName = Field(description="Which Sarvam API. STT covers 23; TTS covers 11."),
    ) -> dict[str, Any]:
        langs = _data.LANGUAGES_BY_API.get(api, [])
        return {
            "api": api,
            "language_count": len(langs),
            "languages": langs,
        }

    @mcp.tool(
        name="sarvam_code_speakers",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "List TTS speakers compatible with a given model tag. The v3 roster "
            "has 38 voices. Returns each speaker with a brief tone hint where available."
        ),
    )
    async def sarvam_code_speakers(
        ctx: Context,
        model: TtsModel = Field(default="bulbul:v3"),
    ) -> dict[str, Any]:
        ids = _data.SPEAKERS_BY_MODEL.get(model, [])
        return {
            "model": model,
            "speaker_count": len(ids),
            "speakers": [
                {"id": s, "tone": _data.SPEAKER_HINTS.get(s, "")}
                for s in ids
            ],
        }

    @mcp.tool(
        name="sarvam_code_pricing",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Current pricing structure for a Sarvam model (or all models if "
            "omitted). Returns billing unit + rate tier. NOTE: this is a "
            "high-level structure; exact per-unit rates depend on your plan "
            "— always confirm at https://dashboard.sarvam.ai before quoting."
        ),
    )
    async def sarvam_code_pricing(
        ctx: Context,
        model: str | None = Field(
            default=None,
            description="Specific model id, e.g. 'bulbul:v3'. Omit to list all.",
        ),
    ) -> dict[str, Any]:
        if model:
            entry = _data.PRICING.get(model)
            if not entry:
                return {
                    "model": model,
                    "found": False,
                    "available_models": sorted(_data.PRICING.keys()),
                    "disclaimer": _data.PRICING_DISCLAIMER,
                }
            return {
                "model": model,
                "found": True,
                **entry,
                "disclaimer": _data.PRICING_DISCLAIMER,
            }
        return {
            "models": _data.PRICING,
            "disclaimer": _data.PRICING_DISCLAIMER,
        }
