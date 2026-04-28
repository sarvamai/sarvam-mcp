"""Just-in-time auth: prompt the user for an API key the first time it's needed.

Why: forcing users to set ``SARVAM_API_KEY`` *before* installing the MCP is a
deployment-time UX wart. With MCP elicitation, the server starts with no key,
and the first tool call asks the client to elicit one. Once supplied, the key
is persisted to ``~/.sarvam/credentials`` and reused on subsequent runs.

Falls back gracefully on clients that don't support elicitation: raises a
clean ``ToolError`` with copy-pasteable setup instructions.
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

# Direct link to create / copy API keys (use everywhere we send users to the dashboard).
DASHBOARD_KEY_MANAGEMENT_URL = "https://dashboard.sarvam.ai/key-management"

# User-facing path (tilde) for messages; use CREDENTIALS_PATH for actual I/O.
_CREDENTIALS_TILDE = "~/.sarvam/credentials"
CREDENTIALS_PATH = Path(_CREDENTIALS_TILDE).expanduser()
SETUP_HELP = (
    "Sarvam API key required. Create or copy one at:\n"
    f"  {DASHBOARD_KEY_MANAGEMENT_URL}\n"
    "Then set it up (easiest first):\n"
    "  1. In your MCP client config, set env: {\"SARVAM_API_KEY\": \"sk_...\"} "
    "(many IDEs have a form for this — no terminal needed)\n"
    "  2. Or run `sarvam-mcp init` once in a terminal (interactive; writes "
    f"{_CREDENTIALS_TILDE} with safe permissions)\n"
    "  3. Advanced: write `api_key = sk_...` into "
    f"{_CREDENTIALS_TILDE} (mode 0600); avoid `echo` with a real key in your shell history"
)


async def ensure_auth(ctx: Context) -> None:
    """Guarantee that ``current_auth()`` will succeed for the rest of this call.

    If no provider is set yet, asks the client (via elicitation) for an API
    key. On success, persists to ``~/.sarvam/credentials`` and installs a
    ``StaticKeyProvider`` for the running server.
    """
    if _current.get() is not None:
        return  # already authenticated for this run

    # Re-check env / credentials in case they were set after server startup.
    refreshed = _try_local_sources()
    if refreshed:
        set_auth(StaticKeyProvider(refreshed))
        return

    # Elicit from the client. Falls back to a clear error if unsupported.
    try:
        result = await ctx.elicit(
            message=(
                "Sarvam needs an API key to make this call. "
                f"Open {DASHBOARD_KEY_MANAGEMENT_URL} (click the link if your app "
                "opens it), copy your API key, and paste it here. It will be "
                f"saved to {_CREDENTIALS_TILDE} so you will not be asked again."
            ),
            response_type=str,
            response_title="Sarvam API Key",
            response_description="Looks like sk_xxxxxxxxxxxx",
        )
    except Exception as exc:  # noqa: BLE001 — older clients / network issues
        logger.warning("Elicitation unavailable: %r — falling back to setup help", exc)
        raise ToolError(SETUP_HELP) from exc

    action = getattr(result, "action", None)
    if action == "decline" or action == "cancel":
        raise ToolError(
            "API key entry was declined. Re-run the tool when you're ready, "
            f"or set it manually:\n{SETUP_HELP}"
        )

    api_key = _extract_value(result)
    if not api_key or not api_key.strip():
        raise ToolError("No API key was provided.\n" + SETUP_HELP)

    api_key = api_key.strip()
    set_auth(StaticKeyProvider(api_key))
    _persist_to_credentials(api_key)
    await ctx.info(
        f"Sarvam API key saved to {_CREDENTIALS_TILDE}. Future tool calls will "
        "use it automatically."
    )


def _try_local_sources() -> str | None:
    """Re-read env + credentials file. Used when the server started without a key."""
    if env := os.environ.get("SARVAM_API_KEY"):
        return env
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


def _extract_value(result: object) -> str | None:
    """Pull the string value out of FastMCP's elicitation response object."""
    data = getattr(result, "data", None)
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        # When response_type=str, FastMCP wraps the value in {"value": "..."}
        for k in ("value", "api_key", "key"):
            if k in data and isinstance(data[k], str):
                return data[k]
    # Some FastMCP versions expose the raw value directly.
    raw_value = getattr(result, "value", None)
    if isinstance(raw_value, str):
        return raw_value
    return None


def _persist_to_credentials(api_key: str) -> None:
    """Write the key to ``~/.sarvam/credentials`` with restrictive permissions."""
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = f"# Sarvam credentials — written by sarvam-mcp\napi_key = {api_key}\n"
    # Write to a temp file then move, so we never leave a partial file behind.
    tmp = CREDENTIALS_PATH.with_suffix(".tmp")
    tmp.write_text(body)
    os.chmod(tmp, 0o600)  # owner read/write only
    tmp.replace(CREDENTIALS_PATH)
