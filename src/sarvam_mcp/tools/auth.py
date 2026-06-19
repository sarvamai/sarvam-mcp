"""API key management tool.

Provides ``sarvam_tools_set_api_key`` so users can paste their API key
directly in chat. The key is saved to ~/.sarvam/credentials for all
future sessions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.auth.api_key import StaticKeyProvider
from sarvam_mcp.auth.context import set_auth

CREDENTIALS_PATH = Path("~/.sarvam/credentials").expanduser()
DASHBOARD_URL = "https://dashboard.sarvam.ai/key-management"


def register(mcp: FastMCP) -> None:
    """Register the API key management tool."""

    @mcp.tool()
    async def sarvam_tools_set_api_key(
        ctx: Context,
        api_key: str = Field(
            default="",
            description=(
                "Your Sarvam API key (starts with sk_). "
                "Leave empty to get instructions on where to find it."
            ),
        ),
    ) -> dict[str, Any]:
        """Set or update your Sarvam API key. Call this if you get an
        authentication error or to configure your key for the first time.

        If called without a key, returns instructions on where to get one.
        If called with a key, saves it globally so you never need to set it again.
        """
        if not api_key or not api_key.strip():
            return {
                "status": "needs_key",
                "message": (
                    "Go to the Sarvam dashboard to get your API key:\n\n"
                    f"  {DASHBOARD_URL}\n\n"
                    "Copy your key (starts with sk_) and call this tool again "
                    "with the key pasted as the `api_key` parameter."
                ),
                "dashboard_url": DASHBOARD_URL,
            }

        key = api_key.strip()
        if not key.startswith("sk_"):
            return {
                "status": "invalid",
                "message": (
                    "That doesn't look like a valid Sarvam API key. "
                    "Keys start with 'sk_'. "
                    f"Get yours at: {DASHBOARD_URL}"
                ),
            }

        set_auth(StaticKeyProvider(key))
        _save_key(key)

        await ctx.info("API key saved to ~/.sarvam/credentials")

        return {
            "status": "saved",
            "message": (
                "API key saved! It's stored at ~/.sarvam/credentials and will "
                "be used automatically for all future sessions. "
                "You can call this tool again anytime to update the key."
            ),
        }


def _save_key(api_key: str) -> None:
    """Save API key to ~/.sarvam/credentials, preserving other settings."""
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)

    preserved: list[str] = []
    if CREDENTIALS_PATH.exists():
        for raw in CREDENTIALS_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, _ = line.partition("=")
            if key.strip() != "api_key":
                preserved.append(raw)

    body = "# Sarvam credentials — managed by sarvam-mcp\n"
    body += f"api_key = {api_key}\n"
    for line in preserved:
        body += f"{line}\n"

    tmp = CREDENTIALS_PATH.with_suffix(".tmp")
    tmp.write_text(body)
    _restrict_permissions(tmp)
    tmp.replace(CREDENTIALS_PATH)


def _restrict_permissions(path: Path) -> None:
    """Set file to owner-only access on all platforms."""
    if sys.platform == "win32":
        # On Windows, use icacls to restrict to current user only.
        import subprocess

        username = os.environ.get("USERNAME", "")
        if username:
            subprocess.run(
                ["icacls", str(path), "/inheritance:r",
                 "/grant:r", f"{username}:(R,W)"],
                capture_output=True,
            )
    else:
        os.chmod(path, 0o600)
