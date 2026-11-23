"""Responses API — ``POST /v2/responses`` (non-streaming).

A stateless alternative to chat completions. Each call stands alone:
``store`` must be false/omitted, ``previous_response_id``/``conversation``/
``background`` are rejected (400) and ``GET /v2/responses/{id}`` always 404s.
``tools`` use the FLAT shape (type, name, description, parameters), not the
nested chat-completions shape. ``n``, ``seed`` are ignored; the open-weight models
reject ``stop`` and ``n``.

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
    NO_LOGPROBS_RESPONSES,
    RESPONSES_EFFORTS,
    V2ChatModel,
    is_provisioned,
    provisioned_access_error,
    provisioned_note,
)
from sarvam_mcp.tools._common import ready_ctx

RESPONSES_PATH = "/v2/responses"
ResponsesEffort = Literal["none", "low", "medium", "high", "max"]


def _output_text(output: Any) -> str:
    """Join the text of every assistant message item in a Responses ``output`` list."""
    texts: list[str] = []
    for item in output or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "output_text" and part.get("text"):
                texts.append(part["text"])
    return "".join(texts)


def _validate(
    *,
    model: str,
    reasoning_effort: str | None,
    top_k: int | None,
    top_logprobs: int | None,
    include: list[str] | None,
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
) -> None:
    for t in tools or []:
        if "function" in t:
            raise ValueError(
                "Responses tools use the flat shape {type, name, description, parameters}; "
                "the nested chat-completions {type, function:{…}} shape returns 400."
            )
    if tool_choice == "required" and not tools:
        raise ValueError("tool_choice='required' needs at least one tool (400 otherwise).")
    if reasoning_effort is not None:
        allowed = RESPONSES_EFFORTS.get(model)
        if allowed is not None and reasoning_effort not in allowed:
            raise ValueError(
                f"{model} accepts reasoning effort {sorted(allowed)} on the Responses API "
                f"(got {reasoning_effort!r}). glm5.3/glm5.3-flash reject the literal 'max'; omit "
                "the field to get their default."
            )
    if top_k is not None and model == "glm5.3":
        raise ValueError("top_k is not supported on the Responses route for glm5.3 (400).")
    if (top_logprobs is not None or include) and model in NO_LOGPROBS_RESPONSES:
        raise ValueError(f"{model} rejects logprobs/top_logprobs on the Responses API (400).")


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_responses_create",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Create a model response with the stateless Responses API (POST /v2/responses). "
            "`input` is a string or a list of input items; replay the whole conversation every call. "
            "Models: sarvam-105b, glm5.3, glm5.3-flash, gemma4, deepseekv4.1-flash-1017, "
            "deepseekv4.1-flash-1017-interactive, sarvam-105b-conversations (serverless) and "
            "deepseekv4-pro, kimi-k3.1-pro, qwen38-27b (PROVISIONED THROUGHPUT — enabled per "
            "organisation; contact Sarvam support, support@sarvam.ai, with the model and expected "
            "volume). Set `max_output_tokens` — there is no default cap.\n\n"
            "Reasoning effort per model: glm5.3 / glm5.3-flash / gemma4 low|high only (the literal "
            "'max' is a 400; omit it for the default); deepseek* low|high|max|none; kimi-k3.1-pro "
            "low|medium|high|max. Logprobs: send `top_logprobs` together with "
            "include=['message.output_text.logprobs'] (not on glm5.3, gemma4, kimi-k3.1-pro)."
        ),
    )
    async def sarvam_responses_create(
        ctx: Context,
        input: str | list[dict[str, Any]] = Field(
            description="Prompt string, or a list of input items."
        ),
        model: V2ChatModel = Field(default="sarvam-105b"),
        instructions: str | None = Field(default=None, description="System-style instructions."),
        max_output_tokens: int | None = Field(default=None, ge=1),
        temperature: float | None = Field(default=None, ge=0.0, le=2.0),
        top_p: float | None = Field(default=None, gt=0.0, le=1.0),
        top_k: int | None = Field(default=None, ge=-1, description="Not supported on glm5.3."),
        frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0),
        presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0),
        reasoning_effort: ResponsesEffort | None = Field(
            default=None, description="Per model — see the tool description."
        ),
        reasoning_summary: Literal["auto", "detailed"] | None = Field(default=None),
        tools: list[dict[str, Any]] | None = Field(
            default=None,
            description="FLAT function tools: {'type':'function','name':…,'description':…,'parameters':{…}}.",
        ),
        tool_choice: str | dict[str, Any] | None = Field(default=None),
        parallel_tool_calls: bool | None = Field(
            default=None, description="False = one tool call per turn on open-weight models."
        ),
        text: dict[str, Any] | None = Field(
            default=None,
            description="Output format, e.g. {'format': {'type': 'json_object'}} or json_schema.",
        ),
        top_logprobs: int | None = Field(default=None, ge=0),
        include: list[str] | None = Field(
            default=None,
            description="e.g. ['message.output_text.logprobs', 'reasoning.encrypted_content'].",
        ),
        extra_body: dict[str, Any] | None = Field(
            default=None, description="Merged into the body; must not repeat a modelled field."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        _validate(
            model=model,
            reasoning_effort=reasoning_effort,
            top_k=top_k,
            top_logprobs=top_logprobs,
            include=include,
            tools=tools,
            tool_choice=tool_choice,
        )
        if is_provisioned(model):
            await ctx.info(provisioned_note(model))

        body: dict[str, Any] = {"model": model, "input": input}
        for key, val in (
            ("instructions", instructions),
            ("max_output_tokens", max_output_tokens),
            ("temperature", temperature),
            ("top_p", top_p),
            ("top_k", top_k),
            ("frequency_penalty", frequency_penalty),
            ("presence_penalty", presence_penalty),
            ("tools", tools),
            ("tool_choice", tool_choice),
            ("parallel_tool_calls", parallel_tool_calls),
            ("text", text),
            ("top_logprobs", top_logprobs),
            ("include", include),
            ("extra_body", extra_body),
        ):
            if val is not None and val != "":
                body[key] = val
        if reasoning_effort or reasoning_summary:
            reasoning: dict[str, str] = {}
            if reasoning_effort:
                reasoning["effort"] = reasoning_effort
            if reasoning_summary:
                reasoning["summary"] = reasoning_summary
            body["reasoning"] = reasoning

        with measure_tool() as metrics:
            try:
                payload, call = await sc.client.post_json(RESPONSES_PATH, json_body=body)
            except SarvamAPIError as exc:
                better = provisioned_access_error(exc, model)
                if better is not None:
                    raise better from exc
                raise
            metrics.merge(call)

        resp = payload if isinstance(payload, dict) else {}
        output = resp.get("output")
        result: dict[str, Any] = {
            "output_text": _output_text(output),
            "output": output,
            "status": resp.get("status"),
            "incomplete_details": resp.get("incomplete_details"),
            "usage": resp.get("usage"),
            "model": resp.get("model"),
            "id": resp.get("id"),
            "observability": metrics.to_response_block(),
        }
        if max_output_tokens is None:
            result["warning"] = "max_output_tokens was not set: Responses has no default cap."
        return result
