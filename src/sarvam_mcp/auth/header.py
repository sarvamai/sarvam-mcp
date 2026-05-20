"""HTTP header-based auth: extract API key from incoming request headers.

Used in hosted/HTTP mode where each request carries the client's own
Sarvam API key in the ``api-subscription-key`` or ``Authorization`` header.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from sarvam_mcp.auth.api_key import StaticKeyProvider
from sarvam_mcp.auth.context import set_auth

logger = logging.getLogger("sarvam_mcp.auth.header")

_HEADER_NAME = "api-subscription-key"
_AUTH_HEADER = "authorization"


def _extract_api_key(request: Request) -> str | None:
    """Extract API key from request headers.

    Priority:
      1. api-subscription-key header (Sarvam convention)
      2. Authorization: Bearer <key>
    """
    if key := request.headers.get(_HEADER_NAME):
        return key.strip()

    auth = request.headers.get(_AUTH_HEADER, "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token

    return None


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that sets per-request auth from HTTP headers.

    Rejects requests without a valid API key with a 401 response, except
    for health-check and well-known endpoints.
    """

    EXEMPT_PATHS = {"/health", "/healthz", "/ready"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        api_key = _extract_api_key(request)
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "missing_api_key",
                    "message": (
                        "Include your Sarvam API key in the `api-subscription-key` header "
                        "or as `Authorization: Bearer <key>`. "
                        "Get one at https://dashboard.sarvam.ai/key-management"
                    ),
                },
            )

        set_auth(StaticKeyProvider(api_key))
        return await call_next(request)
