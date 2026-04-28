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

    The server does **not** fail when ``SARVAM_API_KEY`` is missing — it starts
    cleanly and the first tool call will elicit the key from the user via MCP
    elicitation (see ``auth/elicit.py``).
    """
    config = Config.load()
    if config.api_key:
        set_auth(StaticKeyProvider(config.api_key))
        auth_status = "configured"
    else:
        auth_status = "deferred (will elicit on first tool call)"

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

    # Composite workflows — chain multiple atomic tools per call.
    from sarvam_mcp.workflows import dub, localize, recall, voice

    voice.register(mcp)
    dub.register(mcp)
    localize.register(mcp)
    recall.register(mcp)

    from sarvam_mcp import code

    code.register(mcp)

    return mcp


def main() -> None:
    """Console entry point for ``uvx sarvam-mcp`` / ``sarvam-mcp``.

    Subcommands:
        (no args)  — run the MCP server over stdio (the default).
        init       — interactive setup: paste your API key in the terminal,
                     it lands in ~/.sarvam/credentials with mode 0600.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        _run_init()
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        stream=sys.stderr,
    )
    server = build_server()
    server.run()


def _run_init() -> None:
    """Interactive ``sarvam-mcp init`` — write the credentials file from a TTY.

    Lives here (instead of a separate `cli/` module) because it's a single
    function and pulling in a CLI framework just for this would be overkill.
    """
    import getpass
    import os
    from pathlib import Path

    creds_path = Path("~/.sarvam/credentials").expanduser()
    print("\nSarvam MCP — first-time setup")
    print("─" * 40)
    print("Get your API key at: https://dashboard.sarvam.ai/key-management\n")
    if creds_path.exists():
        print(f"⚠  {creds_path} already exists. Overwrite? [y/N] ", end="", flush=True)
        if input().strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return

    api_key = getpass.getpass("Paste your Sarvam API key (input hidden): ").strip()
    if not api_key:
        print("No key entered — aborting.")
        sys.exit(1)

    region = input("Region [in]: ").strip() or "in"

    creds_path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# Sarvam credentials — written by `sarvam-mcp init`\n"
        f"api_key = {api_key}\n"
        f"region = {region}\n"
    )
    creds_path.write_text(body)
    os.chmod(creds_path, 0o600)
    print(f"\n✓ Credentials saved to {creds_path}")
    print("  Permissions: 0600 (owner-only)")
    print(f"  Region:      {region}")
    print("\nYou can now point Cursor / Claude Desktop at sarvam-mcp without setting env vars.")


if __name__ == "__main__":
    main()
