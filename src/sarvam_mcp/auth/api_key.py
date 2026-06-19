"""Static API key auth provider for outbound Sarvam API calls."""

from __future__ import annotations


class StaticKeyProvider:
    """Wraps an API key (sk_...) for outbound requests to api.sarvam.ai.

    All outbound requests use the ``api-subscription-key`` header.
    """

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("API key is empty.")
        self._key = api_key

    async def headers(self, *, scope: str | None = None) -> dict[str, str]:  # noqa: ARG002
        return {"api-subscription-key": self._key}

    async def refresh(self) -> None:
        return None

    @property
    def principal(self) -> str:
        suffix = self._key[-4:] if len(self._key) >= 4 else "****"
        return f"key:****{suffix}"
