"""Just-in-time auth gate for tool calls.

Every runtime tool calls ``await ensure_auth(ctx)`` (via ``ready_ctx``)
before hitting the Sarvam API.  If no auth provider is set yet, this
module checks for a stored API key in env vars or ``~/.sarvam/credentials``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastmcp import Context
from fastmcp.exceptions import ToolError

from sarvam_mcp.auth.api_key import StaticKeyProvider
from sarvam_mcp.auth.context import _current, set_auth

logger = logging.getLogger("sarvam_mcp.auth")

DASHBOARD_URL = "https://dashboard.sarvam.ai/key-management"

_CREDENTIALS_TILDE = "~/.sarvam/credentials"
CREDENTIALS_PATH = Path(_CREDENTIALS_TILDE).expanduser()


async def ensure_auth(ctx: Context) -> None:  # noqa: ARG001
    """Guarantee that ``current_auth()`` will succeed for this call.

    Checks SARVAM_API_KEY env var first, then stored credentials file.
    If nothing is available, raises a ToolError directing the user to
    set their API key.
    """
    if _current.get() is not None:
        return

    api_key = _resolve_api_key()
    if api_key:
        set_auth(StaticKeyProvider(api_key))
        return

    raise ToolError(
        "No API key found. Call the `sarvam_tools_set_api_key` tool to set "
        "your key — it will guide you through getting one and saves it "
        "globally so you only need to do this once."
    )


def _resolve_api_key() -> str | None:
    """Try to find an API key from env var or credentials file."""
    env_key = os.environ.get("SARVAM_API_KEY")
    if env_key:
        return env_key

    return _read_key_from_credentials()


def _read_key_from_credentials() -> str | None:
    """Read ``api_key`` from ``~/.sarvam/credentials``."""
    if not CREDENTIALS_PATH.exists():
        return None
    for raw in CREDENTIALS_PATH.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "api_key":
            return value.strip().strip('"').strip("'")
    return None
