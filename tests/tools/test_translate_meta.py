"""The translate tool's input hint must reflect the default model's real limit.

`mayura:v1` (the default) caps input at ~1000 chars; only `sarvam-translate:v1`
allows ~2000. The field description must not advertise the higher limit as if
it applied to the default.
"""

from __future__ import annotations

from sarvam_mcp.server import build_server


async def test_translate_input_hint_mentions_default_model_limit():
    server = build_server()
    tool = next(t for t in await server.list_tools() if t.name == "sarvam_tools_translate")
    desc = tool.parameters["properties"]["input"]["description"]
    assert "1000" in desc, "input hint should state mayura:v1's ~1000-char limit"
