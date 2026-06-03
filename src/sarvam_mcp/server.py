"""FastMCP server entry point. ``sarvam-mcp`` console script lands here."""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.auth import StaticKeyProvider, set_auth
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient

logger = logging.getLogger("sarvam_mcp")


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[ServerContext]:
    """Build shared deps once at server start; tear down at shutdown.

    The server starts cleanly even without a stored token — the first tool
    call will direct the user to ``sarvam_tools_auth_login``.
    """
    config = Config.load()

    # Check for a stored OAuth token from a previous login.
    from sarvam_mcp.tools.auth import try_stored_token

    stored = try_stored_token()
    if stored:
        set_auth(StaticKeyProvider(stored))
        auth_status = "configured (stored token)"
    else:
        auth_status = "deferred (will prompt on first tool call)"

    client = SarvamClient(config.base_url, region=config.region)
    sink = build_sink(config.output_mode, config.base_path)
    ctx = ServerContext(config=config, client=client, audio_sink=sink)
    logger.info(
        "sarvam-mcp ready · base_url=%s region=%s output_mode=%s base_path=%s auth=%s",
        config.base_url,
        config.region,
        config.output_mode,
        config.base_path,
        auth_status,
    )
    try:
        yield ctx
    finally:
        await client.aclose()


def build_server() -> FastMCP:
    """Construct the FastMCP server with all tools registered."""
    mcp = FastMCP("sarvam-mcp", lifespan=_lifespan)

    # Auth tools — login + status
    from sarvam_mcp.tools import auth

    auth.register(mcp)

    # Atomic tools — registered eagerly. Each module exposes ``register(mcp)``.
    from sarvam_mcp.tools import (
        language,
        llm,
        pronunciation,
        stt,
        translate,
        transliterate,
        tts,
        vision,
    )

    stt.register(mcp)
    tts.register(mcp)
    translate.register(mcp)
    transliterate.register(mcp)
    language.register(mcp)
    llm.register(mcp)
    vision.register(mcp)
    pronunciation.register(mcp)

    from sarvam_mcp import code, workflows

    code.register(mcp)
    workflows.voice.register(mcp)
    workflows.dub.register(mcp)
    workflows.localize.register(mcp)
    workflows.recall.register(mcp)

    return mcp


def main() -> None:
    """Console entry point for ``uvx sarvam-mcp`` / ``sarvam-mcp``.

    Subcommands:
        (no args)  — run the MCP server over stdio (the default).
        login      — interactive OAuth login: opens your browser, catches
                     the callback, and saves the token to ~/.sarvam/credentials.
    """
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help", "help"}:
        _print_help()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "login":
        _run_login()
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        stream=sys.stderr,
    )
    server = build_server()
    server.run()


def _print_help() -> None:
    """Print CLI help without starting the MCP server."""
    print(
        """sarvam-mcp - Official Sarvam AI MCP server

Usage:
  sarvam-mcp              Run the MCP server over stdio
  sarvam-mcp login        Log in with browser OAuth and save credentials
  sarvam-mcp --help       Show this help

Use this command as an MCP server entry point from clients such as Claude
Desktop, Cursor, Windsurf, and other MCP-compatible tools.
"""
    )


def _run_login() -> None:
    """Interactive ``sarvam-mcp login`` — OAuth flow from the terminal."""
    import asyncio

    from sarvam_mcp.tools.auth import persist_token, try_stored_token

    print("\nSarvam MCP — OAuth login")
    print("─" * 40)

    existing = try_stored_token()
    if existing:
        print("You already have a stored token.")
        print("Re-authenticate? [y/N] ", end="", flush=True)
        if input().strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return

    print("Opening browser for Sarvam login...\n")

    async def _do_login() -> str:
        from unittest.mock import AsyncMock

        from sarvam_mcp.tools.auth import _run_oauth_flow

        mock_ctx = AsyncMock()
        mock_ctx.info = AsyncMock(side_effect=lambda msg: print(f"  {msg}"))
        return await _run_oauth_flow(mock_ctx)

    try:
        token = asyncio.run(_do_login())
    except Exception as exc:
        print(f"\nLogin failed: {exc}")
        sys.exit(1)

    persist_token(token)
    print(f"\n✓ Token saved to ~/.sarvam/credentials")
    print("  Permissions: 0600 (owner-only)")
    print("\nYou can now use sarvam-mcp without additional setup.")


if __name__ == "__main__":
    main()
