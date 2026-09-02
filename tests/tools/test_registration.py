"""Smoke test: every expected tool registers on the FastMCP server.

This is the minimum bar for "ships" — if a tool fails to import or
register, the server won't start and Claude Desktop will fail silently.
"""

from __future__ import annotations

EXPECTED_TOOLS = {
    # API key management
    "sarvam_tools_set_api_key",
    # Build-time helpers — no Sarvam API call / no auth required
    "sarvam_code_api_reference",
    "sarvam_code_languages",
    "sarvam_code_pricing",
    "sarvam_code_recommend_model",
    "sarvam_code_snippet",
    "sarvam_code_speakers",
    "sarvam_code_validate_request",
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
    "sarvam_tools_vision_job_status",
    "sarvam_tools_pronunciation_list",
    "sarvam_tools_pronunciation_get",
    "sarvam_tools_pronunciation_create",
    "sarvam_tools_pronunciation_delete",
    # Maintenance
    "sarvam_tools_upgrade",
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
    assert not missing, f"Tools failed to register: {sorted(missing)}"

    unexpected = names - EXPECTED_TOOLS
    assert not unexpected, f"Registered tools missing from EXPECTED_TOOLS: {sorted(unexpected)}"
