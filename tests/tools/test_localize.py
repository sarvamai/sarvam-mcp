"""Localize JSON through the registered MCP tool with mocked HTTP."""

import json
from contextlib import asynccontextmanager

import pytest
from fastmcp import Client, FastMCP

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.workflows import localize


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Hello", "Namaste"),
        ({"greetings": ["Hello", 123]}, {"greetings": ["Namaste", 123]}),
    ],
    ids=["root-string", "nested-string"],
)
async def test_localize_json_preserves_shape(tmp_path, httpx_mock, source, expected):
    src = tmp_path / "messages.en-IN.json"
    dst = tmp_path / "messages.hi-IN.json"
    src.write_text(json.dumps(source))
    httpx_mock.add_response(
        method="POST", url="https://api.sarvam.ai/translate", json={"translated_text": "Namaste"}
    )

    @asynccontextmanager
    async def lifespan(_server):
        client = SarvamClient("https://api.sarvam.ai")
        try:
            yield ServerContext(Config(base_path=tmp_path), client, build_sink("files", tmp_path))
        finally:
            await client.aclose()

    server = FastMCP("localize-test", lifespan=lifespan)
    localize.register(server)
    async with Client(server) as client:
        result = await client.call_tool(
            "sarvam_tools_localize",
            {"source_path": str(src), "target_language_code": "hi-IN"},
        )

    assert result.data["strings_translated"] == 1
    assert result.data["output_path"] == str(dst)
    assert json.loads(dst.read_text()) == expected
    assert json.loads(src.read_text()) == source
