"""Model discovery — ``GET /v2/models`` and ``GET /v2/models/{model_id}``.

Serverless models (``access: standard``) are open to every key. Provisioned Throughput
models (``access: provisioned``) are enabled per organisation: ``deepseekv4-pro`` is listed
for every key but returns 400 without access; ``kimi-k3.1-pro``, ``qwen38-27b``, ``clef`` and
``embeddinggemma-2`` are NOT listed (and 404) until Sarvam enables them for your org.
Contact Sarvam support to get access.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._chat_models import (
    PROVISIONED_MODELS,
    SERVERLESS_MODELS,
    SUPPORT_EMAIL,
    SUPPORT_URL,
)
from sarvam_mcp.tools._common import ready_ctx

MODELS_PATH = "/v2/models"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_list_models",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "List the chat/Token Factory models your API key can use (GET /v2/models), or inspect "
            "one with `model_id` (GET /v2/models/{model_id}). Each has an id (case-sensitive) and "
            "`access`: standard (serverless — any key) or provisioned (Provisioned Throughput — "
            "enabled per organisation). The result also lists documented Provisioned Throughput "
            "models your org does NOT have yet (`provisioned_without_access`) — to get one, contact "
            "Sarvam support (support@sarvam.ai) with the model and your expected volume."
        ),
    )
    async def sarvam_list_models(
        ctx: Context,
        model_id: str | None = Field(
            default=None, description="Return just this model (case-sensitive id)."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            if model_id:
                payload, call = await sc.client.get_json(f"{MODELS_PATH}/{model_id}")
                metrics.merge(call)
                return {
                    "model": payload,
                    "observability": metrics.to_response_block(),
                }
            payload, call = await sc.client.get_json(MODELS_PATH)
            metrics.merge(call)
        body = payload if isinstance(payload, dict) else {}
        models = body.get("data") or []
        listed = {m.get("id") for m in models if isinstance(m, dict)}
        missing = {m: api for m, api in PROVISIONED_MODELS.items() if m not in listed}
        result: dict[str, Any] = {
            "count": len(models),
            "models": models,
            "serverless_models_documented": sorted(SERVERLESS_MODELS),
            "observability": metrics.to_response_block(),
        }
        result["deepseekv4-pro_note"] = (
            "deepseekv4-pro is listed for every key; a 400 'not enabled for your organisation' on "
            "use means your org lacks Provisioned Throughput access for it."
        )
        if missing:
            result["provisioned_without_access"] = [
                {"model": m, "api": api} for m, api in sorted(missing.items())
            ]
            result["how_to_get_access"] = (
                "These models run on Provisioned Throughput: capacity is set up per workload and "
                f"enabled per organisation. Contact Sarvam support ({SUPPORT_EMAIL}, {SUPPORT_URL}) "
                "with the model you need and your expected volume. Without access, deepseekv4-pro "
                "returns 400 and the others 404."
            )
        return result
