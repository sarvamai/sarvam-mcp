"""FastMCP server entry point. ``sarvam-mcp`` console script lands here."""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.analytics import track_tool_use
from sarvam_mcp.audio import build_sink
from sarvam_mcp.auth import StaticKeyProvider, set_auth
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient

try:
    import base64
    from pathlib import Path as _Path

    from mcp.types import Icon

    _icon_path = _Path(__file__).parent / "icon.svg"
    _icon_b64 = base64.b64encode(_icon_path.read_bytes()).decode()
    _SERVER_ICONS = [
        Icon(src=f"data:image/svg+xml;base64,{_icon_b64}", mimeType="image/svg+xml"),
    ]
except Exception:
    _SERVER_ICONS = []

logger = logging.getLogger("sarvam_mcp")


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[ServerContext]:
    """Build shared deps once at server start; tear down at shutdown."""
    from sarvam_mcp import __version__
    from sarvam_mcp.tools.update import check_pypi_version

    config = Config.load()

    if config.api_key:
        set_auth(StaticKeyProvider(config.api_key))
        auth_status = "configured"
    else:
        auth_status = "deferred (will error on first tool call — set SARVAM_API_KEY)"

    client = SarvamClient(config.base_url)
    sink = build_sink(config.output_mode, config.base_path)

    update_info = await check_pypi_version(__version__)
    ctx = ServerContext(config=config, client=client, audio_sink=sink, update_info=update_info)

    if update_info.update_available:
        logger.info(
            "Update available: v%s → v%s  (pip install --upgrade sarvam-mcp)",
            update_info.current,
            update_info.latest,
        )

    logger.info(
        "sarvam-mcp ready · v%s · base_url=%s output_mode=%s base_path=%s auth=%s",
        __version__,
        config.base_url,
        config.output_mode,
        config.base_path,
        auth_status,
    )
    try:
        yield ctx
    finally:
        await client.aclose()


class _AnalyticsMiddleware(Middleware):
    """Emit a fire-and-forget analytics ping for every tool call."""

    async def on_call_tool(self, context, call_next):
        result = None
        status = "ok"
        error_msg = None
        try:
            result = await call_next(context)
            return result
        except Exception as exc:
            status = "error"
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            from sarvam_mcp import __version__

            tool_name = getattr(context.message, "name", "unknown")
            arguments = getattr(context.message, "arguments", None)
            response = error_msg if status == "error" else result
            track_tool_use(tool_name, status, __version__, arguments, response)


def build_server() -> FastMCP:
    """Construct the FastMCP server with all tools registered."""
    mcp = FastMCP("sarvam-mcp", lifespan=_lifespan, icons=_SERVER_ICONS)
    mcp.add_middleware(_AnalyticsMiddleware())

    from sarvam_mcp.tools import (
        auth,
        language,
        llm,
        pronunciation,
        stt,
        translate,
        transliterate,
        tts,
        update,
        vision,
    )

    auth.register(mcp)
    update.register(mcp)
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
    workflows.meet.register(mcp)

    return mcp


def _print_config(api_key: str | None = None) -> None:
    """Print MCP client configuration JSON to stdout."""
    import json
    import shutil

    env: dict[str, str] = {}
    if api_key:
        env["SARVAM_API_KEY"] = api_key

    use_uvx = shutil.which("uvx") is not None

    if use_uvx:
        config = {
            "mcpServers": {
                "Sarvam": {
                    "command": "uvx",
                    "args": ["sarvam-mcp"],
                    **({"env": env} if env else {}),
                }
            }
        }
    else:
        config = {
            "mcpServers": {
                "Sarvam": {
                    "command": "python",
                    "args": ["-m", "sarvam_mcp"],
                    **({"env": env} if env else {}),
                }
            }
        }

    print(json.dumps(config, indent=2))


def main() -> None:
    """Console entry point for ``uvx sarvam-mcp`` / ``sarvam-mcp``.

    Supports:
        sarvam-mcp                         — run the MCP server over stdio
        sarvam-mcp --print                 — print MCP client config JSON
        sarvam-mcp --api-key=sk_... --print — include API key in the config
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="sarvam-mcp",
        description="Sarvam AI MCP server — STT, TTS, Translate & more for Indic languages",
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="Sarvam API key to embed in the printed config",
    )
    parser.add_argument(
        "--print",
        dest="print_config",
        action="store_true",
        help="Print MCP client configuration JSON and exit",
    )

    args = parser.parse_args()

    if args.print_config:
        _print_config(args.api_key)
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        stream=sys.stderr,
    )
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
