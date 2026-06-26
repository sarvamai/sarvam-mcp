"""Unit tests for the pronunciation dictionary tool functions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastmcp import Client, FastMCP

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.tools import pronunciation

BASE = "https://api.sarvam.ai"
PRONDICT_BASE = f"{BASE}/text-to-speech/pronunciation-dictionary"


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[ServerContext]:
    client = SarvamClient(BASE)
    config = Config(api_key="sk_test_key_for_unit_tests_abcd")
    sink = build_sink("files", None)
    ctx = ServerContext(config=config, client=client, audio_sink=sink)
    try:
        yield ctx
    finally:
        await client.aclose()


@pytest.fixture
def mcp_server():
    server = FastMCP("test-pronunciation", lifespan=_lifespan)
    pronunciation.register(server)
    return server


async def test_pronunciation_list_returns_dictionaries(mcp_server, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=PRONDICT_BASE,
        json={"dictionary_count": 2, "dictionaries": ["dict_abc", "dict_def"]},
        headers={"x-request-id": "req_list_01"},
    )
    async with Client(mcp_server) as client:
        result = await client.call_tool("sarvam_tools_pronunciation_list", {})

    assert not result.is_error
    data = result.data
    assert data["dictionary_count"] == 2
    assert data["dictionaries"] == ["dict_abc", "dict_def"]
    assert "observability" in data


async def test_pronunciation_list_empty(mcp_server, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=PRONDICT_BASE,
        json={"dictionary_count": 0, "dictionaries": []},
    )
    async with Client(mcp_server) as client:
        result = await client.call_tool("sarvam_tools_pronunciation_list", {})

    assert not result.is_error
    assert result.data["dictionary_count"] == 0
    assert result.data["dictionaries"] == []


async def test_pronunciation_get_returns_entries(mcp_server, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=f"{PRONDICT_BASE}/dict_abc",
        json={"pronunciations": {"hi-IN": {"Sarvam": "Saarvam"}}},
        headers={"x-request-id": "req_get_01"},
    )
    async with Client(mcp_server) as client:
        result = await client.call_tool("sarvam_tools_pronunciation_get", {"dictionary_id": "dict_abc"})

    assert not result.is_error
    data = result.data
    assert data["dictionary_id"] == "dict_abc"
    assert "raw" in data
    assert "observability" in data


async def test_pronunciation_create_returns_payload(mcp_server, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=PRONDICT_BASE,
        json={"dictionary_id": "dict_new", "status": "created"},
        headers={"x-request-id": "req_create_01"},
    )
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "sarvam_tools_pronunciation_create",
            {"entries": {"Sarvam": "Saarvam", "CEO": "see ee oh"}, "language_code": "hi-IN"},
        )

    assert not result.is_error
    data = result.data
    assert "raw" in data
    assert "observability" in data


async def test_pronunciation_create_sends_json_file(mcp_server, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=PRONDICT_BASE,
        json={"dictionary_id": "dict_new"},
    )
    async with Client(mcp_server) as client:
        await client.call_tool(
            "sarvam_tools_pronunciation_create",
            {"entries": {"AI": "ay eye"}, "language_code": "en-IN"},
        )

    request = httpx_mock.get_request()
    assert request.method == "POST"
    # Multipart body should contain a JSON file with the pronunciations
    body = request.content.decode("utf-8", errors="replace")
    assert "en-IN" in body
    assert "ay eye" in body


async def test_pronunciation_delete_returns_confirmation(mcp_server, httpx_mock):
    httpx_mock.add_response(
        method="DELETE",
        url=f"{PRONDICT_BASE}?dict_id=dict_abc",
        json={"status": "deleted"},
        headers={"x-request-id": "req_del_01"},
    )
    async with Client(mcp_server) as client:
        result = await client.call_tool("sarvam_tools_pronunciation_delete", {"dictionary_id": "dict_abc"})

    assert not result.is_error
    data = result.data
    assert data["dictionary_id"] == "dict_abc"
    assert data["deleted"] is True
    assert "observability" in data


async def test_pronunciation_delete_sends_dict_id_param(mcp_server, httpx_mock):
    httpx_mock.add_response(
        method="DELETE",
        url=f"{PRONDICT_BASE}?dict_id=dict_xyz",
        json={},
    )
    async with Client(mcp_server) as client:
        await client.call_tool("sarvam_tools_pronunciation_delete", {"dictionary_id": "dict_xyz"})

    request = httpx_mock.get_request()
    assert request.method == "DELETE"
    assert "dict_id=dict_xyz" in str(request.url)
