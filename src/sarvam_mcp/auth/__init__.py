"""Auth: API-key provider + elicit-on-demand flow + HTTP header auth."""

from sarvam_mcp.auth.api_key import StaticKeyProvider
from sarvam_mcp.auth.context import current_auth, set_auth
from sarvam_mcp.auth.header import APIKeyAuthMiddleware

__all__ = [
    "APIKeyAuthMiddleware",
    "StaticKeyProvider",
    "current_auth",
    "set_auth",
]
