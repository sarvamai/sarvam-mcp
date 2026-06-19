"""Self-update check + upgrade tool.

On every server startup the lifespan fires ``check_pypi_version`` which
hits the PyPI JSON API once.  The result is stashed on ``ServerContext``
so the ``sarvam_tools_upgrade`` tool can report / trigger an upgrade
without a second network call.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import httpx
from fastmcp import Context, FastMCP
from packaging.version import Version

from sarvam_mcp.tools._common import server_ctx

logger = logging.getLogger("sarvam_mcp.update")

PYPI_URL = "https://pypi.org/pypi/sarvam-mcp/json"
PACKAGE_NAME = "sarvam-mcp"


@dataclass
class UpdateInfo:
    """Result of the startup PyPI check."""

    current: str
    latest: str | None = None
    update_available: bool = False
    check_error: str | None = None


async def check_pypi_version(current_version: str, *, timeout: float = 5.0) -> UpdateInfo:
    """Non-blocking PyPI version lookup.  Returns ``UpdateInfo``; never raises."""
    info = UpdateInfo(current=current_version)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            resp = await client.get(PYPI_URL)
            resp.raise_for_status()
            latest = resp.json()["info"]["version"]
            info.latest = latest
            info.update_available = Version(latest) > Version(current_version)
    except Exception as exc:
        info.check_error = str(exc)
        logger.debug("PyPI version check failed (non-fatal): %s", exc)
    return info


def _run_upgrade() -> tuple[bool, str]:
    """Upgrade sarvam-mcp using the appropriate method (uvx or pip)."""
    import shutil

    if shutil.which("uv") and _is_uvx_install():
        return _upgrade_uvx()
    return _upgrade_pip()


def _is_uvx_install() -> bool:
    """Heuristic: if the executable lives in a uv/tools directory, it's a uvx install."""
    exe = sys.executable
    return "uv" in exe and "tools" in exe


def _upgrade_uvx() -> tuple[bool, str]:
    """Upgrade via uv tool upgrade."""
    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", PACKAGE_NAME],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def _upgrade_pip() -> tuple[bool, str]:
    """Upgrade via pip install --upgrade."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def register(mcp: FastMCP) -> None:
    """Register the upgrade tool."""

    @mcp.tool()
    async def sarvam_tools_upgrade(
        ctx: Context,
        confirm_upgrade: bool = False,
    ) -> dict[str, Any]:
        """Check for updates and upgrade sarvam-mcp to the latest version.

        Call this when the user asks to update, upgrade, or check for newer
        versions of the sarvam MCP server.

        Set ``confirm_upgrade=True`` to actually perform the upgrade.
        After upgrading, restart the MCP server for changes to take effect.
        """
        sc = server_ctx(ctx)
        info: UpdateInfo | None = sc.update_info

        if info is None:
            return {
                "status": "unknown",
                "message": "Version check was skipped or hasn't completed yet.",
            }

        if info.check_error:
            return {
                "status": "check_failed",
                "current_version": info.current,
                "error": info.check_error,
                "message": (
                    f"Couldn't reach PyPI to check for updates: {info.check_error}\n"
                    f"You're on v{info.current}. "
                    "You can manually run: uv tool upgrade sarvam-mcp (or pip install --upgrade sarvam-mcp)"
                ),
            }

        if not info.update_available:
            return {
                "status": "up_to_date",
                "current_version": info.current,
                "latest_version": info.latest,
                "message": f"You're on the latest version (v{info.current}).",
            }

        if not confirm_upgrade:
            return {
                "status": "update_available",
                "current_version": info.current,
                "latest_version": info.latest,
                "message": (
                    f"A new version of sarvam-mcp is available: "
                    f"v{info.current} → v{info.latest}\n\n"
                    "Call this tool again with confirm_upgrade=True to upgrade now, "
                    "or run manually:\n"
                    f"  uv tool upgrade {PACKAGE_NAME}\n"
                    f"  pip install --upgrade {PACKAGE_NAME}"
                ),
            }

        await ctx.info(f"Upgrading sarvam-mcp to v{info.latest} ...")
        success, output = _run_upgrade()

        if success:
            return {
                "status": "upgraded",
                "current_version": info.current,
                "new_version": info.latest,
                "message": (
                    f"Upgraded sarvam-mcp from v{info.current} to v{info.latest}.\n"
                    "Please restart the MCP server for the new version to take effect."
                ),
                "pip_output": output,
            }

        return {
            "status": "upgrade_failed",
            "current_version": info.current,
            "latest_version": info.latest,
            "error": output,
            "message": (
                f"Automatic upgrade failed.\n\n"
                "Try manually:\n"
                f"  uv tool upgrade {PACKAGE_NAME}\n"
                f"  pip install --upgrade {PACKAGE_NAME}\n\n"
                f"Error: {output}"
            ),
        }
