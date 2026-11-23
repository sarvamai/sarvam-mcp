"""``sarvam_code_*`` documentation tools.

Five tools exposed (plus snippets/recommend/validate in snippets.py):
  - sarvam_code_api_reference  — endpoint shapes (params, response, gotchas)
  - sarvam_code_languages      — supported language codes per API
  - sarvam_code_speakers       — TTS speakers per model tag
  - sarvam_code_pricing        — INR prices per plan (docs-synced)
  - sarvam_code_rate_limits    — per-plan rate limits per API

Source-of-truth data lives in ``code/_data.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.code import _data

# ---- Type literals -------------------------------------------------------

ApiName = Literal[
    "stt", "tts", "translate", "transliterate",
    "lid", "llm", "vision",
]
EndpointPath = Literal[
    "/speech-to-text",
    "/speech-to-text/job/v1",
    "/speech-to-text-realtime/ws",
    "/text-to-speech",
    "/translate",
    "/transliterate",
    "/text-lid",
    "/text-analytics",
    "/v1/chat/completions",
    "/v2/chat/completions",
    "/v2/responses",
    "/v2/models",
    "/v2/embeddings",
    "/v2/systemone",
    "/v2/dictate",
    "/v2/dictate/jobs",
    "/voices/create",
    "/voices/clone",
    "/voices/watermark/detect",
    "/doc-ai/v1/job/parse",
    "/doc-ai/v1/job/extract",
    "/doc-ai/v1/job/classify",
    "/doc-ai/v1/job/split",
    "/translate/document/jobs",
    "/dubbing/jobs",
    "/text-to-speech/pronunciation-dictionary",
    "/text-to-speech/ws",
]
TtsModel = Literal["bulbul:v3", "bulbul:v4-flash"]
Plan = Literal["payg", "pro", "growth", "business"]


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
            "List TTS speakers compatible with a given model tag. Speaker IDs are "
            "model-specific: bulbul:v3 has 37 short-name voices; bulbul:v4-flash has "
            "222 persona IDs (`<voice>_<lang>_<style>`; Assamese voices are not "
            "included — contact Sarvam for access). Returns each speaker with a "
            "brief tone hint where available."
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
            "INR pricing (excl. GST) for a Sarvam model/API, or all of them if omitted, mirroring "
            "docs.sarvam.ai/api/getting-started/pricing (reviewed 2026-11-23). Per-minute / per-1,000-char / "
            "per-page services carry rates for the Pay-as-you-go, Pro, Growth (and where published, Business) "
            "plans; token models carry input / cached-input / output per 1M tokens. Pass `plan` to get just "
            "that plan's rate. Also returns plan fees and the deprecated-model list. Confirm live rates at "
            "https://dashboard.sarvam.ai before quoting."
        ),
    )
    async def sarvam_code_pricing(
        ctx: Context,
        model: str | None = Field(
            default=None,
            description="Model/API id, e.g. 'bulbul:v4-flash', 'sarvam-105b', 'dictate', 'dubbing'. Omit to list all.",
        ),
        plan: Plan | None = Field(
            default=None,
            description="payg | pro | growth | business — return only this plan's rate where the rate varies by plan.",
        ),
    ) -> dict[str, Any]:
        def project(entry: dict[str, Any]) -> dict[str, Any]:
            by_plan = entry.get("rates_inr_by_plan")
            if plan and by_plan is not None:
                out = {k: v for k, v in entry.items() if k != "rates_inr_by_plan"}
                out["plan"] = plan
                out["rate_inr"] = by_plan.get(plan)
                if by_plan.get(plan) is None:
                    out["rate_note"] = "No published rate for this plan — see the dashboard or contact Sarvam."
                return out
            return dict(entry)

        if model:
            entry = _data.PRICING.get(model)
            if not entry:
                deprecated = _data.DEPRECATED_MODELS.get(model)
                return {
                    "model": model,
                    "found": False,
                    **({"deprecated": deprecated} if deprecated else {}),
                    "available_models": sorted(_data.PRICING.keys()),
                    "disclaimer": _data.PRICING_DISCLAIMER,
                }
            return {
                "model": model,
                "found": True,
                **project(entry),
                **(
                    {"provisioned_throughput": _data.PROVISIONED_THROUGHPUT_NOTE}
                    if entry.get("access") == "provisioned"
                    else {}
                ),
                "disclaimer": _data.PRICING_DISCLAIMER,
            }
        return {
            "plans": _data.PLANS,
            "provisioned_throughput": _data.PROVISIONED_THROUGHPUT_NOTE,
            "models": {k: project(v) for k, v in _data.PRICING.items()},
            "deprecated_models": _data.DEPRECATED_MODELS,
            "disclaimer": _data.PRICING_DISCLAIMER,
        }

    @mcp.tool(
        name="sarvam_code_rate_limits",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Published per-plan rate limits (Pay-as-you-go / Pro / Growth) for a Sarvam API, or all if omitted — "
            "STT, TTS, Dictate, voice cloning, translate, LLMs, dubbing, Document AI. Keys: stt_rest, stt_batch, "
            "tts_websocket, dictate_clip, llm_sarvam_105b, doc_ai_extract, … Use these to size retry/backoff and "
            "concurrency. 429 = rate limited, 503 = load shedding, 402 = credits exhausted."
        ),
    )
    async def sarvam_code_rate_limits(
        ctx: Context,
        api: str | None = Field(
            default=None,
            description="Key such as 'stt_rest', 'tts_websocket', 'llm_sarvam_105b', 'doc_ai_extract'. Omit for all.",
        ),
    ) -> dict[str, Any]:
        if api:
            entry = _data.RATE_LIMITS.get(api)
            if not entry:
                return {
                    "api": api, "found": False,
                    "available": sorted(_data.RATE_LIMITS.keys()),
                    "disclaimer": _data.RATE_LIMITS_DISCLAIMER,
                }
            return {"api": api, "found": True, **entry, "disclaimer": _data.RATE_LIMITS_DISCLAIMER}
        return {"limits": _data.RATE_LIMITS, "disclaimer": _data.RATE_LIMITS_DISCLAIMER}
