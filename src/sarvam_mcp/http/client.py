"""Sarvam HTTP client — retry, observability, auth injection.

One instance per server, injected into tools via FastMCP's lifespan context.
Tools call ``client.post_json(...)``, ``client.post_multipart(...)``, or
``client.stream_ws(...)`` and never touch headers/auth themselves.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx

from sarvam_mcp import __version__
from sarvam_mcp.auth.context import current_auth
from sarvam_mcp.http.errors import (
    SarvamAPIError,
    SarvamAuthError,
    SarvamBadRequestError,
    SarvamRateLimitError,
)
from sarvam_mcp.http.retry import retry_async
from sarvam_mcp.observability import CallMetrics, metrics_from_response_headers

DEFAULT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
USER_AGENT = f"sarvam-mcp/{__version__}"


class SarvamClient:
    """Thin wrapper over httpx that injects auth + parses Sarvam errors."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- request shapes -------------------------------------------------

    async def post_json(
        self,
        path: str,
        *,
        json_body: Mapping[str, Any],
        scope: str | None = None,
    ) -> tuple[Any, CallMetrics]:
        return await self._do_request(
            "POST", path, json=dict(json_body), scope=scope
        )

    async def post_multipart(
        self,
        path: str,
        *,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        scope: str | None = None,
    ) -> tuple[Any, CallMetrics]:
        return await self._do_request(
            "POST",
            path,
            data=dict(data) if data else None,
            files=dict(files) if files else None,
            scope=scope,
        )

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        scope: str | None = None,
    ) -> tuple[Any, CallMetrics]:
        return await self._do_request(
            "GET", path, params=dict(params) if params else None, scope=scope
        )

    async def delete_json(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        scope: str | None = None,
    ) -> tuple[Any, CallMetrics]:
        return await self._do_request(
            "DELETE", path, params=dict(params) if params else None, scope=scope
        )

    async def put_blob(
        self,
        url: str,
        content: bytes,
        *,
        content_type: str = "application/octet-stream",
        extra_headers: dict[str, str] | None = None,
        timeout: float = 300.0,
    ) -> CallMetrics:
        """PUT raw bytes to a presigned Azure Blob SAS URL.

        No Sarvam auth is injected — the SAS token is embedded in the URL.
        """
        headers: dict[str, str] = {
            "x-ms-blob-type": "BlockBlob",
            "Content-Type": content_type,
        }
        if extra_headers:
            headers.update(extra_headers)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout)
        ) as blob_client:
            response = await blob_client.put(url, content=content, headers=headers)

        metrics = CallMetrics()
        metrics.status_code = response.status_code
        if not response.is_success:
            raise SarvamAPIError(
                f"Blob upload failed ({response.status_code}): "
                f"{response.text[:500]}",
                status_code=response.status_code,
                request_id=None,
                body=response.text,
            )
        return metrics

    @asynccontextmanager
    async def stream_ws(
        self,
        url: str,
        *,
        scope: str | None = None,
    ) -> AsyncIterator[Any]:
        """Open a WebSocket against ``url`` (full URL, not a path) with auth headers.

        The implementation lives here — but tools should rarely call this
        directly; ``tools/tts.py`` is the single consumer for now.
        """
        # Lazy import: websockets isn't needed for non-streaming tools.
        import websockets

        provider = current_auth()
        headers = await provider.headers(scope=scope)
        async with websockets.connect(url, additional_headers=headers) as ws:
            yield ws

    # ---- internals ------------------------------------------------------

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        scope: str | None = None,
    ) -> tuple[Any, CallMetrics]:
        provider = current_auth()
        auth_headers = await provider.headers(scope=scope)

        async def send() -> httpx.Response:
            resp = await self._client.request(
                method,
                path,
                json=json,
                data=data,
                files=files,
                params=params,
                headers=auth_headers,
            )
            # Trigger retry for transient 5xx via raise_for_status.
            if resp.status_code in (500, 502, 503, 504):
                resp.raise_for_status()
            return resp

        try:
            response = await retry_async(send)
        except httpx.HTTPStatusError as exc:
            # Retries exhausted — fall through to typed error mapping below.
            response = exc.response
        metrics = metrics_from_response_headers(dict(response.headers))
        metrics.status_code = response.status_code

        if response.is_success:
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.json(), metrics
            # Binary (audio, etc.) — caller decides how to handle.
            return response.content, metrics

        await self._raise_for_error(response, metrics)
        # Unreachable
        raise AssertionError("unreachable")

    async def _raise_for_error(
        self, response: httpx.Response, metrics: CallMetrics
    ) -> None:
        body_text = response.text
        message = _extract_error_message(body_text) or response.reason_phrase
        kwargs = dict(
            status_code=response.status_code,
            request_id=metrics.request_id,
            body=body_text,
        )
        if response.status_code in (401, 403):
            raise SarvamAuthError(message, **kwargs)
        if response.status_code == 400:
            raise SarvamBadRequestError(message, **kwargs)
        if response.status_code == 429:
            retry_after = _maybe_float(response.headers.get("retry-after"))
            raise SarvamRateLimitError(message, retry_after=retry_after, **kwargs)
        raise SarvamAPIError(message, **kwargs)


def _extract_error_message(body_text: str) -> str | None:
    if not body_text:
        return None
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        return body_text[:500]
    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                inner = value.get("message") or value.get("detail")
                if isinstance(inner, str):
                    return inner
    return body_text[:500]


def _maybe_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
