"""sarvam_tools_llm_complete — response handling."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastmcp import Client, FastMCP

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.tools import llm

CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"


@asynccontextmanager
async def _client_for(tmp_path):
    cfg = Config(
        api_key="sk_x",
        base_url="https://api.sarvam.ai",
        base_path=tmp_path,
        output_mode="files",
    )
    sc = ServerContext(
        config=cfg,
        client=SarvamClient(cfg.base_url),
        audio_sink=build_sink("files", tmp_path),
    )

    @asynccontextmanager
    async def lifespan(_s):
        yield sc

    mcp = FastMCP("test", lifespan=lifespan)
    llm.register(mcp)
    try:
        async with Client(mcp) as client:
            yield client
    finally:
        await sc.client.aclose()


async def test_stream_true_raises_clear_error(httpx_mock, tmp_path):
    # Per the Sarvam docs, stream=True returns server-sent events
    # (text/event-stream), which the client surfaces as raw bytes.
    httpx_mock.add_response(
        method="POST",
        url=CHAT_URL,
        status_code=200,
        content=b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n',
        headers={"content-type": "text/event-stream"},
    )
    async with _client_for(tmp_path) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "sarvam_tools_llm_complete",
                {"messages": [{"role": "user", "content": "hi"}], "stream": True},
            )
    msg = str(exc_info.value)
    assert "stream=false" in msg
    # Not the opaque AttributeError that leaked before the fix.
    assert "has no attribute" not in msg


async def test_json_response_returns_content(httpx_mock, tmp_path):
    httpx_mock.add_response(
        method="POST",
        url=CHAT_URL,
        status_code=200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "नमस्ते"}, "finish_reason": "stop"}],
            "model": "sarvam-30b",
        },
    )
    async with _client_for(tmp_path) as client:
        result = await client.call_tool(
            "sarvam_tools_llm_complete",
            {"messages": [{"role": "user", "content": "hi"}]},
        )
    assert result.structured_content["content"] == "नमस्ते"
