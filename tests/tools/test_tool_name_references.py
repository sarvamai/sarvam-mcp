"""Every `sarvam_*` tool name mentioned in a tool description must be real.

Tool descriptions and parameter descriptions are read by the LLM to decide
which tool to call and how to chain them. A stale name like
``sarvam_stt_batch_submit`` (missing the ``tools_`` namespace) sends the
agent after a tool that doesn't exist, so the guidance silently breaks.
"""

from __future__ import annotations

import re

from sarvam_mcp.server import build_server

# Matches a full namespaced reference (`sarvam_tools_x`, `sarvam_code_x`) as
# well as a stale/wrong one (`sarvam_stt_x`). The negative lookahead stops the
# match before a `*`, so the namespace-wildcard phrases ``sarvam_tools_*`` /
# ``sarvam_code_*`` are captured as the bare namespaces and skipped below.
_TOOL_REF = re.compile(r"sarvam_[a-z0-9_]+(?<!_)")

# Namespace wildcards, not references to a specific tool.
_NAMESPACE_WILDCARDS = {"sarvam_tools", "sarvam_code"}


def _descriptions(tool) -> list[str]:
    texts: list[str] = []
    if tool.description:
        texts.append(tool.description)
    props = (tool.parameters or {}).get("properties", {})
    for prop in props.values():
        desc = prop.get("description")
        if desc:
            texts.append(desc)
    return texts


async def test_tool_descriptions_only_reference_real_tools():
    server = build_server()
    tools = await server.list_tools()
    registered = {t.name for t in tools}

    bad: list[str] = []
    for tool in tools:
        for text in _descriptions(tool):
            for ref in _TOOL_REF.findall(text):
                # Skip `sarvam_tools_*` / `sarvam_code_*` wildcard phrasing.
                if ref in _NAMESPACE_WILDCARDS:
                    continue
                if ref not in registered:
                    bad.append(f"{tool.name}: references unknown tool '{ref}'")

    assert not bad, "Tool descriptions reference tools that aren't registered:\n" + "\n".join(bad)
