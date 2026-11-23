"""Sarvam LLM chat completions — OpenAI-compatible."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.http.errors import SarvamAPIError
from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._chat_models import (
    is_provisioned,
    provisioned_access_error,
    provisioned_note,
)
from sarvam_mcp.tools._common import ChatModel, SarvamLLM, ready_ctx

CHAT_PATH = "/v1/chat/completions"
CHAT_V2_PATH = "/v2/chat/completions"
# Models proven on the v1 endpoint keep using it; every other model needs v2.
V1_MODELS = frozenset(SarvamLLM.__args__)  # type: ignore[attr-defined]

ChatRole = Literal["system", "user", "assistant"]
# V1 accepts low/medium/high; V2 models additionally take none/max (per-model —
# e.g. kimi-k3.1-pro rejects "none"; the API returns 400 listing valid values).
ReasoningEffort = Literal["none", "low", "medium", "high", "max"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_llm_complete",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Generate chat completions with Sarvam's Indic-tuned LLM.\n\n"
            "Models:\n"
            "- `sarvam-105b` (default) — 128K context, best for complex reasoning, "
            "coding, long-context analysis, agentic tool use.\n"
            "- `sarvam-105b-conversations` — 32K context, post-trained for "
            "real-time dialogue and voice agents; more natural/colloquial Indic "
            "replies. Same price as sarvam-105b. Prefer this one for low-latency "
            "conversational loops (e.g. behind sarvam_tools_voice).\n"
            "- Open-weight models via /v2/chat/completions: `glm5.3`, `glm5.3-flash`, "
            "`gemma4`, `deepseekv4.1-flash-1017`, `deepseekv4.1-flash-1017-interactive` "
            "(serverless) and `deepseekv4-pro`, `kimi-k3.1-pro`, `qwen38-27b` "
            "(PROVISIONED THROUGHPUT — enabled per organisation: contact Sarvam support, "
            "support@sarvam.ai, with the model and expected volume).\n\n"
            "For the full V2 contract (logprobs, session affinity, image input, extra_body, "
            "per-model validation) use sarvam_tools_chat_v2_complete.\n\n"
            "Supports 23 Indic languages with native, romanized, and "
            "code-mixed styles. OpenAI-compatible message format, including "
            "function calling (`tools`/`tool_choice`) and structured output "
            "(`response_format`)."
        ),
    )
    async def sarvam_llm_complete(
        ctx: Context,
        messages: list[dict[str, Any]] = Field(
            description=(
                "OpenAI-style messages: [{'role': 'system'|'user'|'assistant', "
                "'content': '...'}, ...]"
            ),
        ),
        model: ChatModel = Field(
            default="sarvam-105b",
            description=(
                "`sarvam-105b` (flagship, 128K ctx), `sarvam-105b-conversations` "
                "(32K ctx, voice/chat-agent tuned), or an open-weight model served "
                "on /v2/chat/completions (glm5.3, glm5.3-flash, gemma4, "
                "deepseekv4.1-flash-1017[-interactive], deepseekv4-pro, kimi-k3.1-pro, "
                "qwen38-27b). IDs are case-sensitive."
            ),
        ),
        temperature: float | None = Field(
            default=None, ge=0.0, le=2.0,
            description=(
                "Omit to use the API default for the model and mode: sarvam-105b = 1.0 with "
                "reasoning on, 0.6 with reasoning off; sarvam-105b-conversations = 0.6; V2 "
                "open-weight models = 1. Prefer changing temperature or top_p, not both."
            ),
        ),
        top_p: float | None = Field(
            default=None, gt=0.0, le=1.0,
            description="Omit to use the API default (v1: 1.0; V2 models: 0.95). >0 and <=1.",
        ),
        max_tokens: int | None = Field(default=None, ge=1),
        reasoning_effort: ReasoningEffort | None = Field(
            default=None,
            description=(
                "sarvam-105b reasons by default even if you don't ask for it, consuming "
                "a variable, often large chunk of max_tokens on hidden reasoning before "
                "any visible content is produced. 'low' reduces that overhead but does "
                "NOT eliminate it — a small max_tokens (e.g. 20-100) can still come back "
                "empty. If you set max_tokens, give it real headroom (300+); omitting "
                "max_tokens entirely is the safest way to always get visible content. "
                "Pass 'none' to switch reasoning off (sent as null on v1; the default temperature then drops "
                "from 1.0 to 0.6 on sarvam-105b). Omit this field to use the API's own default effort."
            ),
        ),
        stream: bool = Field(
            default=False,
            description="Streaming via MCP isn't useful for chat — keep False unless testing.",
        ),
        stop: list[str] | None = Field(
            default=None, description="Up to 4 stop sequences.",
        ),
        frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0),
        presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0),
        seed: int | None = Field(
            default=None, description="Beta: best-effort deterministic sampling.",
        ),
        n: int | None = Field(
            default=None, ge=1, le=1,
            description="Only 1 is supported — the API returns 400 for n > 1 (since 2026-11-07).",
        ),
        top_k: int | None = Field(
            default=None, ge=-1,
            description="V2 models only. -1 or >=1 enables top-k; 0 is rejected. Not supported on glm5.3.",
        ),
        repetition_penalty: float | None = Field(
            default=None, gt=0.0, le=2.0, description="V2 models only. >0 and <=2.",
        ),
        parallel_tool_calls: bool | None = Field(
            default=None, description="V2 models only. False limits the model to one tool call per turn.",
        ),
        tools: list[dict[str, Any]] = Field(
            default_factory=list,
            description="OpenAI-style function-calling tool definitions.",
        ),
        tool_choice: str | dict[str, Any] | None = Field(
            default=None,
            description="'auto' | 'none' | 'required' | {'type': 'function', 'function': {'name': ...}}.",
        ),
        response_format: dict[str, Any] | None = Field(
            default=None,
            description=(
                "Structured output: {'type': 'json_object'} or "
                "{'type': 'json_schema', 'json_schema': {...}}."
            ),
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            # temperature/top_p are only sent when set so the API's per-model defaults apply
            # (sarvam-105b: 1.0 reasoning on / 0.6 off; conversations: 0.6).
            "stream": stream,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if top_p is not None:
            body["top_p"] = top_p
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if reasoning_effort is not None:
            body["reasoning_effort"] = reasoning_effort
        if stop is not None:
            body["stop"] = stop
        if frequency_penalty is not None:
            body["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            body["presence_penalty"] = presence_penalty
        if seed is not None:
            body["seed"] = seed
        if n is not None:
            body["n"] = n
        use_v2 = model not in V1_MODELS
        if is_provisioned(model):
            await ctx.info(provisioned_note(model))
        if use_v2:
            if top_k is not None:
                body["top_k"] = top_k
            if repetition_penalty is not None:
                body["repetition_penalty"] = repetition_penalty
            if parallel_tool_calls is not None:
                body["parallel_tool_calls"] = parallel_tool_calls
        elif any(v is not None for v in (top_k, repetition_penalty, parallel_tool_calls)):
            raise ValueError(
                "top_k, repetition_penalty and parallel_tool_calls are only supported on "
                "V2 models (glm5.3, glm5.3-flash, gemma4, deepseek*, kimi*, qwen*)."
            )
        warnings: list[str] = []
        if model == "sarvam-105b-conversations" and reasoning_effort not in (None, "none"):
            # Docs: a level is accepted but ignored — the model runs with reasoning off only.
            warnings.append(
                "sarvam-105b-conversations runs with reasoning off only; the reasoning level is "
                "accepted but ignored."
            )
        if not use_v2:
            if reasoning_effort == "max":
                raise ValueError(
                    "reasoning_effort 'max' needs a V2 model; v1 takes low/medium/high or 'none'."
                )
            if reasoning_effort == "none":
                # v1 switches reasoning off with an explicit null (and the default temperature
                # then drops from 1.0 to 0.6 on sarvam-105b).
                body["reasoning_effort"] = None
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if response_format is not None:
            body["response_format"] = response_format

        with measure_tool() as metrics:
            try:
                payload, call = await sc.client.post_json(
                    CHAT_V2_PATH if use_v2 else CHAT_PATH, json_body=body
                )
            except SarvamAPIError as exc:
                better = provisioned_access_error(exc, model)
                if better is not None:
                    raise better from exc
                raise
            metrics.merge(call)

        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        finish_reason = choice.get("finish_reason")
        content = message.get("content") or ""

        result: dict[str, Any] = {
            "content": content,
            "role": message.get("role", "assistant"),
            "tool_calls": message.get("tool_calls"),
            "finish_reason": finish_reason,
            "usage": payload.get("usage"),
            "model": payload.get("model"),
            "observability": metrics.to_response_block(),
        }
        if warnings:
            result["warnings"] = warnings
        if finish_reason == "length":
            if not content:
                result["truncation_warning"] = (
                    "max_tokens was reached before any visible content was produced — "
                    "consumed entirely by sarvam-105b's reasoning. Raise max_tokens "
                    "substantially (300+) and/or pass reasoning_effort='low'; omitting "
                    "max_tokens entirely is the most reliable fix."
                )
            else:
                result["truncation_warning"] = (
                    "Output was truncated because max_tokens was reached. "
                    "Increase max_tokens or omit it for the full response."
                )
        return result
