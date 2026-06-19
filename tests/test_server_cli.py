from __future__ import annotations

import sys

import pytest

from sarvam_mcp import server


def test_help_flag_prints_usage_without_starting_server(monkeypatch, capsys):
    def fail_build_server():
        raise AssertionError("help must not start the MCP server")

    monkeypatch.setattr(sys, "argv", ["sarvam-mcp", "--help"])
    monkeypatch.setattr(server, "build_server", fail_build_server)

    with pytest.raises(SystemExit) as exc_info:
        server.main()

    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "sarvam-mcp" in output
