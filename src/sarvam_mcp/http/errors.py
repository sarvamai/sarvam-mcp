"""Typed errors raised by SarvamClient. Tools surface these to the agent."""

from __future__ import annotations


class SarvamAPIError(Exception):
    """Base for all errors returned by the Sarvam API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        self.body = body


class SarvamAuthError(SarvamAPIError):
    """401/403 — bad or missing credentials."""


class SarvamRateLimitError(SarvamAPIError):
    """429 — quota exceeded. ``retry_after`` may be set if the API returned it."""

    def __init__(self, *args, retry_after: float | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class SarvamBadRequestError(SarvamAPIError):
    """400 — caller-side validation problem."""


class SarvamConnectionError(SarvamAPIError):
    """Network-level failure (DNS, connection refused, timeout) — the request
    never produced an HTTP response, even after retries. ``status_code`` is
    ``None`` since no response was received."""
