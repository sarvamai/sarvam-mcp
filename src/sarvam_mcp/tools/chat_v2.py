"""Chat Completion V2 — ``POST /v2/chat/completions``.

The OpenAI-compatible chat API for Sarvam-105B and the open-weight Token Factory
models. Unlike ``sarvam_tools_llm_complete`` (which targets the legacy /v1 endpoint for the
Sarvam models and only routes here as a convenience) this tool exposes the whole V2 contract:
log probabilities, ``extra_body``, session affinity, ``developer``/``tool`` roles, image input
and the per-model reasoning rules.

Provisioned Throughput models (``deepseekv4-pro``, ``kimi-k3.1-pro``, ``qwen38-27b``) are
enabled per organisation — contact Sarvam support to get access.
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.http.errors import SarvamAPIError
from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._chat_models import (
    CANNOT_DISABLE_THINKING,
    MEDIUM_EFFORT_MODELS,
    NO_LOGPROBS_CHAT,
    SESSION_AFFINITY_MODELS,
    STOP_MAX_FOUR,
    TEXT_ONLY_MODELS,
    V2ChatModel,
    is_provisioned,
    provisioned_access_error,
    provisioned_note,
)
from sarvam_mcp.tools._common import ready_ctx

CHAT_V2_PATH = "/v2/chat/completions"
V2Effort = Literal["none", "low", "medium", "high", "max"]
_ROLES = {"system", "developer", "user", "assistant", "tool"}


def _validate_messages(messages: list[dict[str, Any]], model: str) -> None:
    if not messages:
        raise ValueError("messages must be a non-empty list.")
    for i, msg in enumerate(messages):
        role = msg.get("role")
        if role not in _ROLES:
            raise ValueError(f"messages[{i}].role must be one of {sorted(_ROLES)}; got {role!r}.")
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            url = (part.get("image_url") or {}).get("url", "")
            if not str(url).startswith("data:image/"):
                raise ValueError(
                    f"messages[{i}]: images must be inline data:image/…;base64,… URLs — remote "
                    "http(s) image URLs are rejected by the API."
                )
            if model in TEXT_ONLY_MODELS:
                raise ValueError(
                    f"{model} is text-only; pick an image-capable model (e.g. gemma4)."
                )


def _validate_request(
    *,
    model: str,
    reasoning_effort: str | None,
    stop: str | list[str] | None,
    logprobs: bool | None,
    top_logprobs: int | None,
    top_k: int | None,
    response_format: dict[str, Any] | None,
    session_id: str | None,
) -> list[str]:
    """Raise on combinations the API rejects; return non-fatal warnings."""
    warnings: list[str] = []
    if reasoning_effort == "none" and model in CANNOT_DISABLE_THINKING:
        raise ValueError(
            f"{model} cannot turn thinking off (reasoning_effort='none' is not accepted). "
            "Use low/high/max, or pick deepseekv4.1-flash-1017, deepseekv4-pro or qwen38-27b."
        )
    if reasoning_effort == "medium" and model not in MEDIUM_EFFORT_MODELS:
        warnings.append(
            f"reasoning_effort='medium' is documented only on {sorted(MEDIUM_EFFORT_MODELS)}; "
            f"{model} may reject it — use low, high or max."
        )
    if model == "sarvam-105b-conversations" and reasoning_effort not in (None, "none"):
        warnings.append(
            "sarvam-105b-conversations runs with reasoning off only; the reasoning level is accepted "
            "but ignored."
        )
    stops = [stop] if isinstance(stop, str) else (stop or [])
    if len(stops) > 4 and model in STOP_MAX_FOUR:
        raise ValueError(f"{model} accepts at most 4 stop sequences (got {len(stops)}).")
    if (logprobs or top_logprobs is not None) and model in NO_LOGPROBS_CHAT:
        raise ValueError(
            f"{model} does not support logprobs/top_logprobs (400) — omit both entirely."
        )
    if top_logprobs is not None and not logprobs:
        raise ValueError("top_logprobs takes effect only with logprobs=True.")
    if top_k == 0:
        raise ValueError("top_k=0 is rejected; use -1 to disable or a value >= 1.")
    if top_k is not None and model == "glm5.3":
        raise ValueError("top_k is not supported on glm5.3.")
    if model == "qwen38-27b" and response_format and reasoning_effort != "none":
        raise ValueError(
            "qwen38-27b structured output needs reasoning_effort='none' (with thinking on the "
            "JSON lands in the reasoning trace and `content` is null)."
        )
    if session_id and model not in SESSION_AFFINITY_MODELS:
        warnings.append(
            f"x-session-affinity is only honoured by gemma4; {model} accepts but ignores it."
        )
    return warnings


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_chat_v2_complete",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Chat Completion V2 (POST /v2/chat/completions) — the OpenAI-compatible API for "
            "`sarvam-105b` and the open-weight Token Factory models. Use this (not "
            "sarvam_tools_llm_complete) when you need V2 features: logprobs, `developer`/`tool` roles, "
            "inline image input, session affinity, `top_k`/`repetition_penalty`, or `extra_body`. "
            "`sarvam-105b-conversations` (32K ctx, reasoning off only) is served here too.\n\n"
            "Serverless (any key): sarvam-105b, sarvam-105b-conversations, glm5.3, glm5.3-flash, "
            "gemma4, deepseekv4.1-flash-1017, "
            "deepseekv4.1-flash-1017-interactive.\n"
            "PROVISIONED THROUGHPUT (enabled per organisation — contact Sarvam support at "
            "support@sarvam.ai with the model and expected volume): deepseekv4-pro, kimi-k3.1-pro, "
            "qwen38-27b. Without access deepseekv4-pro returns 400 and the others 404; run "
            "sarvam_tools_list_models to see what your key can use.\n\n"
            "Per-model rules (checked before the call): `n` must be 1; reasoning_effort 'none' only "
            "on deepseekv4.1-flash-1017[-interactive], deepseekv4-pro, qwen38-27b (glm5.3, "
            "glm5.3-flash, kimi-k3.1-pro always think; gemma4 is off unless set); 'medium' only on "
            "sarvam-105b, deepseek*, kimi-k3.1-pro, qwen38-27b; logprobs not on glm5.3/kimi-k3.1-pro; "
            "image input only on glm5.3-flash, gemma4, deepseek V4.1 Flash, kimi-k3.1-pro (also "
            "video), qwen38-27b (inline data: URIs); sarvam-105b/glm5.3/gemma4 allow 4 stop "
            "sequences max. "
            "Set `max_tokens` explicitly — reasoning tokens count against it and only glm5.3 has a "
            "(2048) default. Prices: see sarvam_code_pricing."
        ),
    )
    async def sarvam_chat_v2_complete(
        ctx: Context,
        model: V2ChatModel = Field(description="Case-sensitive model ID (see tool description)."),
        messages: list[dict[str, Any]] = Field(
            description=(
                "Non-empty conversation. Roles: system, developer, user, assistant, tool. Content is "
                "a string or parts [{'type':'text',…},{'type':'image_url','image_url':{'url':"
                "'data:image/png;base64,…'}}]."
            ),
        ),
        max_tokens: int | None = Field(
            default=None,
            ge=1,
            description="Includes reasoning tokens. Only glm5.3 defaults to 2048 — set it explicitly.",
        ),
        temperature: float | None = Field(
            default=None, ge=0.0, le=2.0, description="API default 1."
        ),
        top_p: float | None = Field(
            default=None, gt=0.0, le=1.0, description="API default 0.95; 0 is rejected on glm5.3."
        ),
        reasoning_effort: V2Effort | None = Field(
            default=None,
            description=(
                "none | low | medium | high | max. Defaults: max on glm5.3 and kimi-k3.1-pro; high on "
                "glm5.3-flash, deepseek*; gemma4 off. 'none' only where thinking can be disabled; "
                "'medium' only on some models."
            ),
        ),
        stop: str | list[str] | None = Field(default=None, description="Stop sequence(s)."),
        seed: int | None = Field(default=None, description="OpenAI-SDK compatibility only."),
        frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0),
        presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0),
        tools: list[dict[str, Any]] | None = Field(
            default=None,
            description="Function tools: [{'type':'function','function':{name,description,parameters}}].",
        ),
        tool_choice: str | dict[str, Any] | None = Field(
            default=None,
            description="none | auto | required | named function. 'required' with no tools is a 400.",
        ),
        parallel_tool_calls: bool | None = Field(
            default=None, description="False limits a turn to a single tool call (all models)."
        ),
        response_format: dict[str, Any] | None = Field(
            default=None,
            description="{'type':'json_object'} or {'type':'json_schema','json_schema':{…}}.",
        ),
        top_k: int | None = Field(
            default=None,
            ge=-1,
            description="-1 disables; >=1 enables. 0 is rejected. Not on glm5.3.",
        ),
        repetition_penalty: float | None = Field(default=None, gt=0.0, le=2.0),
        logprobs: bool | None = Field(
            default=None, description="Not supported on glm5.3 or kimi-k3.1-pro (400)."
        ),
        top_logprobs: int | None = Field(
            default=None, ge=0, description="Needs logprobs=True. Omit entirely on glm5.3."
        ),
        session_id: str | None = Field(
            default=None,
            description=(
                "Sent as the x-session-affinity header: one stable opaque ID (e.g. a UUID, no "
                "personal data) per conversation. Only gemma4 uses it; others ignore it."
            ),
        ),
        extra_body: dict[str, Any] | None = Field(
            default=None,
            description="Model-specific options merged into the body. Must not repeat a top-level field.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        _validate_messages(messages, model)
        warnings = _validate_request(
            model=model,
            reasoning_effort=reasoning_effort,
            stop=stop,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            top_k=top_k,
            response_format=response_format,
            session_id=session_id,
        )
        if tool_choice == "required" and not tools:
            raise ValueError("tool_choice='required' needs at least one tool (400 otherwise).")
        if is_provisioned(model):
            await ctx.info(provisioned_note(model))

        body: dict[str, Any] = {"model": model, "messages": messages}
        for key, val in (
            ("max_tokens", max_tokens),
            ("temperature", temperature),
            ("top_p", top_p),
            ("reasoning_effort", reasoning_effort),
            ("stop", stop),
            ("seed", seed),
            ("frequency_penalty", frequency_penalty),
            ("presence_penalty", presence_penalty),
            ("tools", tools),
            ("tool_choice", tool_choice),
            ("parallel_tool_calls", parallel_tool_calls),
            ("response_format", response_format),
            ("top_k", top_k),
            ("repetition_penalty", repetition_penalty),
            ("logprobs", logprobs),
            ("top_logprobs", top_logprobs),
            ("extra_body", extra_body),
        ):
            if val is not None:
                body[key] = val
        headers = {"x-session-affinity": session_id} if session_id else None

        with measure_tool() as metrics:
            try:
                payload, call = await sc.client.post_json(
                    CHAT_V2_PATH, json_body=body, headers=headers
                )
            except SarvamAPIError as exc:
                better = provisioned_access_error(exc, model)
                if better is not None:
                    raise better from exc
                raise
            metrics.merge(call)

        resp = payload if isinstance(payload, dict) else {}
        choice = (resp.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        finish = choice.get("finish_reason")
        content = message.get("content")
        result: dict[str, Any] = {
            "content": content or "",
            "reasoning_content": message.get("reasoning_content"),
            "role": message.get("role", "assistant"),
            "tool_calls": message.get("tool_calls"),
            "finish_reason": finish,
            "logprobs": choice.get("logprobs"),
            "usage": resp.get("usage"),
            "model": resp.get("model"),
            "id": resp.get("id"),
            "system_fingerprint": resp.get("system_fingerprint"),
            "observability": metrics.to_response_block(),
        }
        if warnings:
            result["warnings"] = warnings
        if finish == "length":
            result["truncation_warning"] = (
                "max_tokens was reached"
                + (" before any visible content" if not content else "")
                + " — reasoning tokens count against max_tokens. Raise it (or lower "
                "reasoning_effort)."
            )
        return result
