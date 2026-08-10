"""Tiny retry helper for transient HTTP failures."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

T = TypeVar("T")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.4,
) -> T:
    """Run ``fn`` with exponential backoff + jitter on transient failures.

    Retries on:
    - ``httpx.TransportError`` (connection-level)
    - ``httpx.HTTPStatusError`` with status in ``RETRYABLE_STATUS``
      (includes 429 rate limits and 5xx server errors)

    For 429 responses, respects the ``Retry-After`` header if present.
    Anything else propagates immediately.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return await fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in RETRYABLE_STATUS or attempt == attempts - 1:
                raise
            last_exc = exc
            if exc.response.status_code == 429:
                retry_after = _parse_retry_after(exc.response.headers.get("retry-after"))
                if retry_after is not None:
                    await asyncio.sleep(min(retry_after, 30.0))
                    continue
        except httpx.TransportError as exc:
            if attempt == attempts - 1:
                raise
            last_exc = exc
        delay = base_delay * (2**attempt) + random.uniform(0, 0.2)
        await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc


def _parse_retry_after(value: str | None) -> float | None:
    """Parse Retry-After header value as seconds."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
