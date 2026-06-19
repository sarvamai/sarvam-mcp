"""``sarvam_code_*`` namespace — builder tools that help devs CREATE
Sarvam-using apps (vs ``sarvam_tools_*`` which INVOKE Sarvam at runtime).

Two families (registered separately so individual modules stay small):

- ``code.docs``   — 4 reference tools (api_reference, languages, speakers,
                    pricing). Backed by hard-coded tables in ``_data.py``.
- ``code.snippets`` — tested code snippets + model recommendation + request
                      validation.
"""

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register all sarvam_code_* tools onto the FastMCP server."""
    from sarvam_mcp.code import docs, snippets

    docs.register(mcp)
    snippets.register(mcp)
