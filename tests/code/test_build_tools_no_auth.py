"""Build-time `sarvam_code_*` tools must work without an API key.

They return static reference data / snippets / heuristics and never call the
Sarvam API, so requiring auth contradicts their documented contract
(`code/__init__.py`, AGENTS.md, and the recommend_model description which
states it "works without an API key").
"""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP

import sarvam_mcp.auth.elicit as elicit
from sarvam_mcp.auth.context import _current
from sarvam_mcp.code import docs, snippets

# (tool_name, arguments) for every build-time tool.
BUILD_TOOLS = [
    ("sarvam_code_snippet", {"api": "tts", "language": "python"}),
    ("sarvam_code_recommend_model", {"task_description": "transcribe Hindi audio"}),
    (
        "sarvam_code_validate_request",
        {"endpoint": "/text-to-speech", "body": {"inputs": ["hi"], "target_language_code": "hi-IN"}},
    ),
    ("sarvam_code_api_reference", {"endpoint": "/text-to-speech"}),
    ("sarvam_code_languages", {"api": "tts"}),
    ("sarvam_code_speakers", {"model": "bulbul:v3"}),
    ("sarvam_code_pricing", {}),
]


@pytest.fixture
def no_auth(monkeypatch, tmp_path):
    """Simulate a fresh user: no provider, no env key, no credentials file."""
    _current.set(None)
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.setattr(elicit, "CREDENTIALS_PATH", tmp_path / "missing" / "credentials")


@pytest.fixture
def code_server():
    mcp = FastMCP("test")
    snippets.register(mcp)
    docs.register(mcp)
    return mcp


@pytest.mark.parametrize("tool_name,arguments", BUILD_TOOLS)
async def test_build_tool_works_without_api_key(code_server, no_auth, tool_name, arguments):
    async with Client(code_server) as client:
        result = await client.call_tool(tool_name, arguments)
    # No exception == no auth gate. Sanity-check it returned structured data.
    assert result.structured_content is not None
