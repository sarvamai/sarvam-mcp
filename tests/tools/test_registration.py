"""Smoke test: every expected tool registers on the FastMCP server.

This is the minimum bar for "ships" — if a tool fails to import or
register, the server won't start and Claude Desktop will fail silently.
"""

from __future__ import annotations

EXPECTED_TOOLS = {
    # API key management
    "sarvam_tools_set_api_key",
    # Atomic — one tool per Sarvam endpoint
    "sarvam_tools_stt_transcribe",
    "sarvam_tools_stt_translate",
    "sarvam_tools_stt_batch_submit",
    "sarvam_tools_stt_batch_status",
    "sarvam_tools_tts_speak",
    "sarvam_tools_tts_stream",
    "sarvam_tools_translate",
    "sarvam_tools_transliterate",
    "sarvam_tools_identify_language",
    "sarvam_tools_text_analytics",
    "sarvam_tools_llm_complete",
    "sarvam_tools_vision_extract",
    # Composite /sv-* workflows
    "sarvam_tools_voice",
    "sarvam_tools_dub",
    "sarvam_tools_localize",
    "sarvam_tools_recall",
}


async def test_all_expected_tools_register():
    from sarvam_mcp.server import build_server

    server = build_server()

    # FastMCP's tool registry: prefer the public API, fall back to internal.
    if hasattr(server, "list_tools"):
        tools = await server.list_tools()
        names = {t.name for t in tools}
    else:  # pragma: no cover — older FastMCP
        names = set(server._tool_manager._tools.keys())  # type: ignore[attr-defined]

    missing = EXPECTED_TOOLS - names
    assert not missing, f"Tools failed to register: {missing}"
