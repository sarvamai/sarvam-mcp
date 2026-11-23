"""Token Factory model facts shared by the chat, responses, decisions and embeddings tools.

Source: docs.sarvam.ai — Chat Completion overview ("V2 models", "V2 feature support",
"V2 behaviour notes"), Open-Weight Models ("Provisioned Throughput"), Responses API.
Reviewed 2026-11-23 against sarvamai/sarvam-fern-config @ c817b5b.

Serverless models work with any API key. **Provisioned Throughput** models are enabled
per organisation: you must contact Sarvam support first.
"""

from __future__ import annotations

from typing import Literal

from sarvam_mcp.http.errors import SarvamAPIError

SUPPORT_EMAIL = "support@sarvam.ai"
SUPPORT_URL = "https://docs.sarvam.ai/api/getting-started/help"

# Models served by POST /v2/chat/completions and POST /v2/responses (IDs are case-sensitive).
# `sarvam-105b-conversations` is also served on /v1/chat/completions; on V2 its reasoning level is
# accepted but ignored (it runs with reasoning off only).
V2ChatModel = Literal[
    "sarvam-105b",
    "sarvam-105b-conversations",
    "glm5.3",
    "glm5.3-flash",
    "gemma4",
    "deepseekv4.1-flash-1017",
    "deepseekv4.1-flash-1017-interactive",
    "deepseekv4-pro",
    "kimi-k3.1-pro",
    "qwen38-27b",
]

SERVERLESS_MODELS = frozenset(
    {
        "sarvam-105b",
        "sarvam-105b-conversations",
        "sarvam-prism",
        "glm5.3",
        "glm5.3-flash",
        "gemma4",
        "deepseekv4.1-flash-1017",
        "deepseekv4.1-flash-1017-interactive",
    }
)

# model id -> the API it is served on. Enabled per organisation; contact support to get access.
PROVISIONED_MODELS: dict[str, str] = {
    "deepseekv4-pro": "Chat Completion V2 and Responses",
    "kimi-k3.1-pro": "Chat Completion V2 and Responses",
    "qwen38-27b": "Chat Completion V2 and Responses",
    "clef": "Decisions API (POST /v2/systemone)",
    "embeddinggemma-2": "Embeddings (POST /v2/embeddings)",
}

# --- capability tables (docs "V2 feature support" + "V2 behaviour notes") --------------------
NO_LOGPROBS_CHAT = frozenset({"glm5.3", "kimi-k3.1-pro"})  # chat: 400
NO_LOGPROBS_RESPONSES = frozenset({"glm5.3", "gemma4", "kimi-k3.1-pro"})  # responses: 400
CANNOT_DISABLE_THINKING = frozenset({"glm5.3", "glm5.3-flash", "kimi-k3.1-pro"})
STOP_MAX_FOUR = frozenset({"sarvam-105b", "glm5.3", "gemma4"})  # >4 -> 400; others accept more
SESSION_AFFINITY_MODELS = frozenset({"gemma4"})  # header ignored elsewhere
TEXT_ONLY_MODELS = frozenset(
    {"sarvam-105b", "sarvam-105b-conversations", "glm5.3", "deepseekv4-pro"}
)  # no image input

# Models where reasoning_effort="medium" is documented to work (chat V2). Elsewhere it is not documented.
MEDIUM_EFFORT_MODELS = frozenset(
    {
        "sarvam-105b",
        "deepseekv4.1-flash-1017",
        "deepseekv4.1-flash-1017-interactive",
        "deepseekv4-pro",
        "kimi-k3.1-pro",
        "qwen38-27b",
    }
)

# `reasoning.effort` accepted on the Responses API, per model.
RESPONSES_EFFORTS: dict[str, frozenset[str]] = {
    "glm5.3": frozenset({"low", "high"}),
    "glm5.3-flash": frozenset({"low", "high"}),
    "gemma4": frozenset({"low", "high"}),
    "deepseekv4.1-flash-1017": frozenset({"none", "low", "high", "max"}),
    "deepseekv4.1-flash-1017-interactive": frozenset({"none", "low", "high", "max"}),
    "deepseekv4-pro": frozenset({"none", "low", "high", "max"}),
    "kimi-k3.1-pro": frozenset({"low", "medium", "high", "max"}),
}


def is_provisioned(model: str) -> bool:
    return model in PROVISIONED_MODELS


def provisioned_note(model: str) -> str:
    api = PROVISIONED_MODELS.get(model, "the Token Factory API")
    return (
        f"`{model}` is on Provisioned Throughput ({api}): capacity is set up for your workload "
        "and enabled per organisation, so it only works once Sarvam has turned it on for your "
        f"org. To get access, contact Sarvam support ({SUPPORT_EMAIL}, {SUPPORT_URL}) with the "
        "model you need and your expected volume."
    )


def provisioned_access_error(exc: SarvamAPIError, model: str) -> SarvamAPIError | None:
    """If ``exc`` looks like "your org lacks access to this provisioned model", return a
    clearer error; otherwise None.

    Without access ``deepseekv4-pro`` returns ``400`` ("…runs on Provisioned Throughput and is
    not enabled for your organisation"); every other provisioned model returns ``404
    not_found_error`` (the same as an unknown model) and is absent from ``GET /v2/models``.
    """
    if not is_provisioned(model):
        return None
    text = f"{exc} {exc.body or ''}".lower()
    denied = exc.status_code == 404 or (
        exc.status_code == 400 and ("provisioned throughput" in text or "not enabled" in text)
    )
    if not denied:
        return None
    return SarvamAPIError(
        f"{exc}\n\n{provisioned_note(model)}",
        status_code=exc.status_code,
        request_id=exc.request_id,
        body=exc.body,
    )
