"""ContextVar carrying the active auth provider for the current request.

Set once at server startup (or lazily via elicitation on first tool call).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sarvam_mcp.auth.api_key import StaticKeyProvider

_current: ContextVar[StaticKeyProvider | None] = ContextVar("sarvam_auth", default=None)


def set_auth(provider: StaticKeyProvider) -> None:
    """Set the active provider for the current async context."""
    _current.set(provider)


def current_auth() -> StaticKeyProvider:
    """Return the active provider, or raise if none has been set."""
    provider = _current.get()
    if provider is None:
        raise RuntimeError(
            "No auth provider configured. Set SARVAM_API_KEY, run `sarvam-mcp init`, "
            "or add ~/.sarvam/credentials before starting the MCP server. API keys: "
            "https://dashboard.sarvam.ai/key-management"
        )
    return provider
