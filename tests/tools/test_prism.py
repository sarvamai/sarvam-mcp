"""Prism decision tool against a mocked Sarvam API.

Calls go through an in-memory MCP client, so argument validation, the tool body
and the response shape are real; only the HTTP layer is faked.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.code.snippets import _recommend
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.tools import prism

URL = "https://api.sarvam.ai/v2/systemone"
TOOL = "sarvam_tools_prism_decide"

QUESTIONS = {
    "refund": {"type": "noul", "instructions": "Is the customer asking for a refund?"},
    "team": {
        "type": "choice",
        "instructions": "Which team owns this?",
        "criteria": {"billing": "Payments and invoices", "tech": "Product bugs"},
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is it?",
        "criteria": ["Can wait", "Needs a reply today", "Needs action now"],
    },
}

API_RESPONSE = {
    "model": "sarvam-prism",
    "answers": {
        "refund": {"type": "noul", "noul": 0.97},
        "team": {
            "type": "choice", "choice": "billing", "confidence": 0.9,
            "probabilities": {"billing": 0.95, "tech": 0.05},
        },
        "urgency": {
            "type": "score", "score": 1.8, "confidence": 0.6,
            "legend": {"0": "Can wait", "1": "Needs a reply today", "2": "Needs action now"},
            "probabilities": {"0": 0.05, "1": 0.2, "2": 0.75},
        },
    },
    "usage": {"input_tokens": 120, "output_tokens": 0},
}


@pytest.fixture
async def mcp(tmp_path: Path) -> AsyncIterator[FastMCP]:
    @asynccontextmanager
    async def lifespan(_server: FastMCP):
        client = SarvamClient("https://api.sarvam.ai")
        try:
            yield ServerContext(
                config=Config(base_path=tmp_path),
                client=client,
                audio_sink=build_sink("files", tmp_path),
            )
        finally:
            await client.aclose()

    server = FastMCP("test", lifespan=lifespan)
    prism.register(server)
    yield server


async def call(mcp: FastMCP, **args: Any) -> dict[str, Any]:
    async with Client(mcp) as client:
        result = await client.call_tool(TOOL, args)
    return result.data


async def test_sends_documented_request_and_returns_api_shape(mcp, httpx_mock):
    httpx_mock.add_response(
        method="POST", url=URL, json=API_RESPONSE, headers={"x-request-id": "req_prism"}
    )

    out = await call(mcp, state="Please refund my duplicate charge, it is urgent", questions=QUESTIONS)

    request = httpx_mock.get_requests()[0]
    assert request.headers["api-subscription-key"] == "sk_test_key_for_unit_tests_abcd"
    assert json.loads(request.content) == {
        "model": "sarvam-prism",
        "state": "Please refund my duplicate charge, it is urgent",
        "questions": QUESTIONS,
    }
    # API fields come back untouched; the only addition is observability.
    assert set(out) == {"model", "answers", "usage", "observability"}
    assert out["model"] == "sarvam-prism"
    assert out["answers"] == API_RESPONSE["answers"]
    assert out["usage"] == {"input_tokens": 120, "output_tokens": 0}
    assert out["observability"]["request_ids"] == ["req_prism"]


async def test_structured_state_is_passed_through_as_json(mcp, httpx_mock):
    httpx_mock.add_response(method="POST", url=URL, json=API_RESPONSE)
    state = {"subject": "Refund", "messages": ["charged twice", "please fix"]}

    await call(mcp, state=state, questions={"refund": QUESTIONS["refund"]})

    assert json.loads(httpx_mock.get_requests()[0].content)["state"] == state


@pytest.mark.parametrize(
    ("questions", "message"),
    [
        ({}, "at least one question"),
        ({"q": {"type": "noul", "instruction": "typo"}}, "unknown key"),
        ({"q": {"type": "NOUL", "instructions": "x"}}, "lowercase"),
        ({"q": {"type": "yesno", "instructions": "x"}}, "'noul', 'choice' or 'score'"),
        ({"q": {"type": "choice", "instructions": "x"}}, "'choice' needs criteria"),
        ({"q": {"type": "choice", "instructions": "x", "criteria": {"a": "only one"}}}, "2-255"),
        ({"q": {"type": "score", "instructions": "x", "criteria": {"a": "b"}}}, "list of 2-10"),
        ({"q": {"type": "score", "instructions": "x", "criteria": ["only one"]}}, "list of 2-10"),
        ({"q": {"type": "score", "instructions": "x", "criteria": list("abcdefghijk")}}, "list of 2-10"),
        ({"q": {"type": "noul", "instructions": "x", "criteria": "yes"}}, "'noul' criteria"),
    ],
)
async def test_invalid_questions_fail_before_any_api_call(mcp, httpx_mock, questions, message):
    with pytest.raises(ToolError, match=message):
        await call(mcp, state="text", questions=questions)

    assert httpx_mock.get_requests() == []


async def test_api_validation_error_surfaces(mcp, httpx_mock):
    httpx_mock.add_response(
        method="POST", url=URL, status_code=422,
        json={"error": {"code": "unprocessable_entity_error", "message": "state is required",
                        "param": "state"}},
    )

    with pytest.raises(ToolError):
        await call(mcp, state="x", questions={"refund": QUESTIONS["refund"]})


def test_recommend_routes_decision_tasks_to_prism():
    result = _recommend("route support tickets with a calibrated yes/no decision")
    assert result["matched"]
    assert result["recommended_model"] == "sarvam-prism"
    assert result["endpoint"] == "/v2/systemone"
