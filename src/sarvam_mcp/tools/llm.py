"""Sarvam LLM chat completions — OpenAI-compatible."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import SarvamLLM, ready_ctx

CHAT_PATH = "/v1/chat/completions"

ChatRole = Literal["system", "user", "assistant"]
ReasoningEffort = Literal["low", "medium", "high"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_llm_complete",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Generate chat completions with Sarvam's Indic-tuned LLM.\n\n"
            "Two models on this endpoint:\n"
            "- `sarvam-105b` (default) — 128K context, best for complex reasoning, "
            "coding, long-context analysis, agentic tool use.\n"
            "- `sarvam-105b-conversations` — 32K context, post-trained for "
            "real-time dialogue and voice agents; more natural/colloquial Indic "
            "replies. Same price as sarvam-105b. Prefer this one for low-latency "
            "conversational loops (e.g. behind sarvam_tools_voice).\n\n"
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
        model: SarvamLLM = Field(
            default="sarvam-105b",
            description=(
                "`sarvam-105b` (flagship, 128K ctx) or `sarvam-105b-conversations` "
                "(32K ctx, tuned for voice/chat-agent workloads)."
            ),
        ),
        temperature: float = Field(default=0.7, ge=0.0, le=2.0),
        top_p: float = Field(default=1.0, ge=0.0, le=1.0),
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
                "Omit this field to use the API's own default effort."
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
            default=None, ge=1, description="Number of completions to generate.",
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
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
        }
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
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if response_format is not None:
            body["response_format"] = response_format

        with measure_tool() as metrics:
            payload, call = await sc.client.post_json(CHAT_PATH, json_body=body)
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
