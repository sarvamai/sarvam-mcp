"""The tool names in the README Tools table must be real registered tools."""

from __future__ import annotations

import re
from pathlib import Path

from sarvam_mcp.server import build_server

README = Path(__file__).resolve().parent.parent / "README.md"


def _readme_table_tool_names() -> list[str]:
    text = README.read_text(encoding="utf-8")
    # Scope to the "## Tools" section only (up to the next "## " heading).
    section = text.split("## Tools", 1)[1].split("\n## ", 1)[0]
    # Each table row's first column is a backticked tool name.
    return re.findall(r"^\|\s*`(sarvam_[a-z_]+)`", section, re.MULTILINE)


async def test_readme_tool_names_are_registered():
    server = build_server()
    registered = {t.name for t in await server.list_tools()}

    names = _readme_table_tool_names()
    assert names, "no tool names parsed from the README Tools table"

    unregistered = [n for n in names if n not in registered]
    assert not unregistered, f"README lists tool names that aren't registered: {unregistered}"
