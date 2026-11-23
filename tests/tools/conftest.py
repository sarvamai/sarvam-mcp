"""Shared fixtures for tool tests that run against a mocked Sarvam API."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient


@pytest.fixture
def make_server(tmp_path: Path) -> Callable[..., FastMCP]:
    """Build a FastMCP server with the given tool modules registered."""

    def _make(*modules: Any) -> FastMCP:
        @asynccontextmanager
        async def lifespan(_server: FastMCP) -> AsyncIterator[ServerContext]:
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
        for module in modules:
            module.register(server)
        return server

    return _make


async def call_tool(server: FastMCP, tool: str, /, **args: Any) -> Any:
    async with Client(server) as client:
        result = await client.call_tool(tool, args)
    return result.data
