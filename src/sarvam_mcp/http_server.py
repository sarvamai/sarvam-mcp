"""Hosted HTTP entry point for sarvam-mcp.

Runs the MCP server over Streamable HTTP transport (FastMCP's built-in ASGI app)
with per-request API key authentication via HTTP headers.

Usage:
    sarvam-mcp-http                     # starts on 0.0.0.0:8000
    PORT=9000 sarvam-mcp-http           # custom port
    uvicorn sarvam_mcp.http_server:app  # production with uvicorn directly
"""

from __future__ import annotations

import logging
import os
import sys

os.environ.setdefault("SARVAM_MCP_TRANSPORT", "http")

from starlette.middleware import Middleware  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

from sarvam_mcp.auth.header import APIKeyAuthMiddleware  # noqa: E402
from sarvam_mcp.server import build_server  # noqa: E402

logger = logging.getLogger("sarvam_mcp.http")

_mcp = build_server()


@_mcp.custom_route("/health", methods=["GET"])
async def health_check(request):  # noqa: ARG001
    return JSONResponse({"status": "ok", "service": "sarvam-mcp"})


@_mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request):  # noqa: ARG001
    return JSONResponse({"status": "ready", "service": "sarvam-mcp"})


_middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "api-subscription-key",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    ),
    Middleware(APIKeyAuthMiddleware),
]

app = _mcp.http_app(path="/mcp", middleware=_middleware)


def main_http() -> None:
    """Console entry point for ``sarvam-mcp-http``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        stream=sys.stderr,
    )

    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    logger.info("Starting sarvam-mcp HTTP server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main_http()
