from __future__ import annotations

import sys

from sarvam_mcp import server


def test_help_flag_prints_usage_without_starting_server(monkeypatch, capsys):
    def fail_build_server():
        raise AssertionError("help must not start the MCP server")

    monkeypatch.setattr(sys, "argv", ["sarvam-mcp", "--help"])
    monkeypatch.setattr(server, "build_server", fail_build_server)

    server.main()

    output = capsys.readouterr().out
    assert "Usage:" in output
    assert "sarvam-mcp login" in output
    assert "Run the MCP server over stdio" in output
