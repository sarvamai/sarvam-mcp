"""Composite ``/sv-*`` workflow tools.

These chain multiple atomic Sarvam APIs into single MCP tools so common
end-to-end flows (voice loops, dubbing, repo localization, indexed recall)
fit in one prompt instead of five.

Each module exposes ``register(mcp)``. ``server.py`` registers them after
the atomic tools so any naming clash falls in favor of the explicit
``sarvam_*`` ones.
"""

from sarvam_mcp.workflows import dub, localize, meet, recall, voice

__all__ = ["dub", "localize", "meet", "recall", "voice"]
