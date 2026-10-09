"""The server lifespan must not block startup on the PyPI update check.

The update lookup is best-effort telemetry; a slow or unreachable PyPI must
never delay the MCP server becoming ready to serve tools. The check runs in
the background and populates ``update_info`` when it finishes.
"""

from __future__ import annotations

import asyncio

from sarvam_mcp.server import _lifespan, build_server
from sarvam_mcp.tools import update as update_mod
from sarvam_mcp.tools.update import UpdateInfo


async def test_startup_does_not_block_on_pypi_check(monkeypatch):
    release = asyncio.Event()
    started = asyncio.Event()

    async def blocking_check(current_version: str, *, timeout: float = 5.0) -> UpdateInfo:
        started.set()
        await release.wait()  # stand in for a slow/unreachable PyPI
        return UpdateInfo(current=current_version, latest="99.0.0", update_available=True)

    monkeypatch.setattr(update_mod, "check_pypi_version", blocking_check)

    server = build_server()
    cm = _lifespan(server)

    # Startup must complete even though the PyPI check is still blocked. If the
    # check were awaited on the startup path, __aenter__ would hang here and
    # wait_for would raise TimeoutError.
    ctx = await asyncio.wait_for(cm.__aenter__(), timeout=2.0)
    try:
        # Startup returned without the check finishing (it's still blocked).
        assert ctx.update_info is None, "startup must not wait for the check to finish"

        # The check is scheduled — it starts once the loop gets a tick.
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set(), "update check should have been scheduled"

        # Let the background check complete; update_info should then populate.
        release.set()
        for _ in range(200):
            if ctx.update_info is not None:
                break
            await asyncio.sleep(0.01)
        assert ctx.update_info is not None
        assert ctx.update_info.update_available
    finally:
        await cm.__aexit__(None, None, None)
