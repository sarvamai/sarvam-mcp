"""Chat Completion V2 tool, Responses validation, model listing and Provisioned Throughput access."""

from __future__ import annotations

import json

import pytest
from fastmcp.exceptions import ToolError

from sarvam_mcp.tools import chat_v2, embeddings, models, prism, responses
from tests.tools.conftest import call_tool

URL = "https://api.sarvam.ai/v2/chat/completions"
MSG = [{"role": "user", "content": "hi"}]
OK = {
    "id": "c1",
    "model": "glm5.3-flash",
    "system_fingerprint": "fp",
    "choices": [
        {
            "finish_reason": "stop",
            "logprobs": {"content": []},
            "message": {"role": "assistant", "content": "hello", "reasoning_content": "thinking…"},
        }
    ],
    "usage": {"completion_tokens_details": {"reasoning_tokens": 3}},
}


async def _chat(make_server, **kw):
    return await call_tool(make_server(chat_v2), "sarvam_tools_chat_v2_complete", **kw)


async def test_v2_tool_hits_v2_endpoint_and_returns_reasoning(make_server, httpx_mock):
    httpx_mock.add_response(url=URL, json=OK)
    out = await _chat(
        make_server, model="glm5.3-flash", messages=MSG, max_tokens=500, reasoning_effort="high"
    )
    req = httpx_mock.get_requests()[0]
    body = json.loads(req.content)
    assert body == {
        "model": "glm5.3-flash",
        "messages": MSG,
        "max_tokens": 500,
        "reasoning_effort": "high",
    }
    assert "x-session-affinity" not in req.headers
    assert out["content"] == "hello" and out["reasoning_content"] == "thinking…"
    assert out["logprobs"] == {"content": []} and out["id"] == "c1"


async def test_v2_conversations_model_is_served_on_v2(make_server, httpx_mock):
    httpx_mock.add_response(url=URL, json=OK)
    await _chat(make_server, model="sarvam-105b-conversations", messages=MSG)
    assert json.loads(httpx_mock.get_requests()[0].content)["model"] == "sarvam-105b-conversations"


async def test_v2_session_affinity_header_and_warning(make_server, httpx_mock):
    httpx_mock.add_response(url=URL, json=OK)
    httpx_mock.add_response(url=URL, json=OK)
    ok = await _chat(make_server, model="gemma4", messages=MSG, session_id="sess-1")
    assert httpx_mock.get_requests()[0].headers["x-session-affinity"] == "sess-1"
    assert "warnings" not in ok
    other = await _chat(make_server, model="glm5.3", messages=MSG, session_id="sess-1")
    assert "only honoured by gemma4" in other["warnings"][0]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"model": "glm5.3", "reasoning_effort": "none"}, "cannot turn thinking off"),
        ({"model": "kimi-k3.1-pro", "reasoning_effort": "none"}, "cannot turn thinking off"),
        ({"model": "glm5.3", "logprobs": True}, "does not support logprobs"),
        (
            {"model": "kimi-k3.1-pro", "top_logprobs": 3, "logprobs": True},
            "does not support logprobs",
        ),
        ({"model": "gemma4", "top_logprobs": 3}, "needs|only with logprobs|logprobs=True"),
        ({"model": "glm5.3", "top_k": 5}, "top_k is not supported"),
        ({"model": "gemma4", "top_k": 0}, "top_k=0"),
        ({"model": "gemma4", "stop": list("abcde")}, "at most 4 stop"),
        (
            {"model": "glm5.3-flash", "stop": list("abcde"), "tool_choice": "required"},
            "needs at least one tool",
        ),
        (
            {"model": "qwen38-27b", "response_format": {"type": "json_object"}},
            "reasoning_effort='none'",
        ),
        ({"model": "glm5.3", "messages": [{"role": "robot", "content": "x"}]}, "role"),
        ({"model": "glm5.3", "messages": []}, "non-empty"),
        (
            {
                "model": "gemma4",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": "https://x.test/a.png"}}
                        ],
                    }
                ],
            },
            "inline data:image",
        ),
        (
            {
                "model": "deepseekv4-pro",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64,AA=="},
                            }
                        ],
                    }
                ],
            },
            "text-only",
        ),
    ],
)
async def test_v2_per_model_rules_fail_before_any_call(make_server, httpx_mock, kwargs, match):
    kwargs = {"messages": MSG, **kwargs}
    with pytest.raises(ToolError, match=match):
        await _chat(make_server, **kwargs)
    assert httpx_mock.get_requests() == []


async def test_v2_qwen_structured_output_with_thinking_off_is_allowed(make_server, httpx_mock):
    httpx_mock.add_response(url=URL, json=OK)
    await _chat(
        make_server,
        model="qwen38-27b",
        messages=MSG,
        reasoning_effort="none",
        response_format={"type": "json_object"},
    )
    assert json.loads(httpx_mock.get_requests()[0].content)["reasoning_effort"] == "none"


@pytest.mark.parametrize(
    ("model", "status", "text"),
    [
        (
            "deepseekv4-pro",
            400,
            "This model runs on Provisioned Throughput and is not enabled for your organisation",
        ),
        ("kimi-k3.1-pro", 404, "model not found"),
        ("qwen38-27b", 404, "model not found"),
    ],
)
async def test_provisioned_model_without_access_says_contact_support(
    make_server, httpx_mock, model, status, text
):
    httpx_mock.add_response(url=URL, status_code=status, json={"error": {"message": text}})
    with pytest.raises(ToolError) as err:
        await _chat(make_server, model=model, messages=MSG)
    msg = str(err.value)
    assert (
        "Provisioned Throughput" in msg and "support@sarvam.ai" in msg and "expected volume" in msg
    )


async def test_ordinary_400_on_provisioned_model_is_not_rewritten(make_server, httpx_mock):
    httpx_mock.add_response(
        url=URL, status_code=400, json={"error": {"message": "top_p must be > 0"}}
    )
    with pytest.raises(ToolError) as err:
        await _chat(make_server, model="deepseekv4-pro", messages=MSG)
    assert "support@sarvam.ai" not in str(err.value)


async def test_serverless_404_is_not_rewritten(make_server, httpx_mock):
    httpx_mock.add_response(url=URL, status_code=404, json={"error": {"message": "unknown model"}})
    with pytest.raises(ToolError) as err:
        await _chat(make_server, model="glm5.3", messages=MSG)
    assert "support@sarvam.ai" not in str(err.value)


# ---- Responses ------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"model": "glm5.3", "reasoning_effort": "max"}, "accepts reasoning effort"),
        ({"model": "gemma4", "reasoning_effort": "max"}, "accepts reasoning effort"),
        ({"model": "kimi-k3.1-pro", "reasoning_effort": "none"}, "accepts reasoning effort"),
        ({"model": "glm5.3", "top_k": 3}, "top_k"),
        ({"model": "gemma4", "top_logprobs": 2}, "rejects logprobs"),
        ({"model": "sarvam-105b", "tool_choice": "required"}, "at least one tool"),
    ],
)
async def test_responses_per_model_rules(make_server, httpx_mock, kwargs, match):
    with pytest.raises(ToolError, match=match):
        await call_tool(
            make_server(responses), "sarvam_tools_responses_create", input="hi", **kwargs
        )
    assert httpx_mock.get_requests() == []


async def test_responses_logprobs_include_and_provisioned_hint(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/responses", json={"output": [], "status": "completed"}
    )
    out = await call_tool(
        make_server(responses),
        "sarvam_tools_responses_create",
        input="hi",
        model="deepseekv4.1-flash-1017",
        top_logprobs=2,
        include=["message.output_text.logprobs"],
        reasoning_effort="none",
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["include"] == ["message.output_text.logprobs"] and body["reasoning"] == {
        "effort": "none"
    }
    assert "max_output_tokens" in out["warning"]
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/responses", status_code=404, json={"error": {"message": "nf"}}
    )
    with pytest.raises(ToolError, match="support@sarvam.ai"):
        await call_tool(
            make_server(responses), "sarvam_tools_responses_create", input="hi", model="qwen38-27b"
        )


# ---- Prism clef / embeddings provisioned hint -----------------------------


async def test_clef_and_embeddings_404_say_contact_support(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/systemone", status_code=404, json={"error": {"message": "nf"}}
    )
    with pytest.raises(ToolError, match="support@sarvam.ai"):
        await call_tool(
            make_server(prism),
            "sarvam_tools_prism_decide",
            state="x",
            model="clef",
            questions={"q": {"type": "noul", "instructions": "yes?"}},
        )
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/embeddings",
        status_code=404,
        json={"error": {"message": "nf"}},
    )
    with pytest.raises(ToolError, match="Provisioned Throughput"):
        await call_tool(make_server(embeddings), "sarvam_tools_embed", input="x")


# ---- model listing --------------------------------------------------------


async def test_list_models_reports_provisioned_models_without_access(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/models",
        json={
            "object": "list",
            "data": [
                {"id": "glm5.3", "access": "standard"},
                {"id": "deepseekv4-pro", "access": "provisioned"},
            ],
        },
    )
    out = await call_tool(make_server(models), "sarvam_tools_list_models")
    missing = {m["model"] for m in out["provisioned_without_access"]}
    assert missing == {"kimi-k3.1-pro", "qwen38-27b", "clef", "embeddinggemma-2"}
    assert "support@sarvam.ai" in out["how_to_get_access"]
    assert "400" in out["deepseekv4-pro_note"]


async def test_list_models_single_model(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/models/glm5.3", json={"id": "glm5.3", "access": "standard"}
    )
    out = await call_tool(make_server(models), "sarvam_tools_list_models", model_id="glm5.3")
    assert out["model"]["id"] == "glm5.3"


# ---- Clef images, Doc AI capabilities, Dictate delete ----------------------


async def test_clef_images_only_as_data_uris(make_server, httpx_mock):
    q = {"q": {"type": "noul", "instructions": "is it a cat?"}}
    with pytest.raises(ToolError, match="Only clef reads images"):
        await call_tool(
            make_server(prism),
            "sarvam_tools_prism_decide",
            state="x",
            questions=q,
            images=["data:image/png;base64,AA=="],
        )
    with pytest.raises(ToolError, match="base64 data URIs"):
        await call_tool(
            make_server(prism),
            "sarvam_tools_prism_decide",
            state="x",
            questions=q,
            model="clef",
            images=["https://x.test/a.png"],
        )
    assert httpx_mock.get_requests() == []
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/systemone", json={"model": "clef", "answers": {}}
    )
    await call_tool(
        make_server(prism),
        "sarvam_tools_prism_decide",
        state="x",
        questions=q,
        model="clef",
        images=["data:image/png;base64,AA=="],
    )
    assert json.loads(httpx_mock.get_requests()[0].content)["images"] == [
        "data:image/png;base64,AA=="
    ]


async def test_vision_capabilities(make_server, httpx_mock):
    from sarvam_mcp.tools import vision

    httpx_mock.add_response(
        url="https://api.sarvam.ai/doc-ai/v1/capabilities",
        json={"api_contract": "v1", "operations": ["split"], "limits": {"max_source_pages": 500}},
    )
    out = await call_tool(make_server(vision), "sarvam_tools_vision_capabilities")
    assert out["limits"] == {"max_source_pages": 500} and out["api_contract"] == "v1"


async def test_dictate_job_delete(make_server, httpx_mock):
    from sarvam_mcp.tools import dictate

    httpx_mock.add_response(
        method="DELETE", url="https://api.sarvam.ai/v2/dictate/jobs/j1", status_code=204
    )
    out = await call_tool(make_server(dictate), "sarvam_tools_dictate_job_delete", job_id="j1")
    assert out["deleted"] is True
