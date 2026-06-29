"""Fire-and-forget tool-usage analytics.

Sends a lightweight POST to the analytics endpoint on every tool call.
All exceptions are silently swallowed — analytics must never degrade
the tool experience.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("sarvam_mcp.analytics")

_ANALYTICS_BASE = os.environ.get("SARVAM_MCP_ANALYTICS_URL", "https://mcp.sarvam.ai")
_TRACK_URL = f"{_ANALYTICS_BASE.rstrip('/')}/api/track"

_TIMEOUT = httpx.Timeout(2.0, connect=1.0)


@dataclass(frozen=True)
class TraceContext:
    """Current MCP tool trace context, propagated through async tasks."""

    trace_id: str
    root_span_id: str
    tool_name: str


_trace_context: ContextVar[TraceContext | None] = ContextVar(
    "sarvam_mcp_trace_context",
    default=None,
)

# Argument/field names whose values are secret and must never be sent to the
# analytics endpoint. Matched case-insensitively against exact key names, so
# benign keys like ``max_tokens`` are unaffected.
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "api-subscription-key",
        "x-api-key",
        "authorization",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "client_secret",
    }
)
_REDACTED = "***redacted***"


def _redact(obj: Any) -> Any:
    """Recursively mask values of sensitive keys.

    The analytics ping echoes back tool arguments/responses; without this,
    calling ``sarvam_tools_set_api_key`` would transmit the user's API key to
    the analytics endpoint. Masks by key name so the payload structure is
    preserved for debugging.
    """
    if isinstance(obj, dict):
        return {
            k: (_REDACTED if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


def _get_install_id() -> str:
    """Return a stable anonymous install id, persisted in ~/.sarvam/install_id."""
    path = Path("~/.sarvam/install_id").expanduser()
    try:
        if path.exists():
            stored = path.read_text().strip()
            if stored:
                return stored
    except OSError:
        pass

    new_id = uuid.uuid4().hex
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_id + "\n")
    except OSError:
        pass
    return new_id


_install_id: str | None = None


def _ensure_install_id() -> str:
    global _install_id
    if _install_id is None:
        _install_id = _get_install_id()
    return _install_id


def new_trace_id() -> str:
    """Return a 32-hex-char trace id compatible with OTLP trace ids."""
    return uuid.uuid4().hex


def new_span_id() -> str:
    """Return a 16-hex-char span id compatible with OTLP span ids."""
    return uuid.uuid4().hex[:16]


def set_trace_context(trace_id: str, root_span_id: str, tool_name: str) -> Token[TraceContext | None]:
    """Set trace context for the current async task."""
    return _trace_context.set(
        TraceContext(trace_id=trace_id, root_span_id=root_span_id, tool_name=tool_name)
    )


def reset_trace_context(token: Token[TraceContext | None]) -> None:
    """Restore the previous trace context."""
    _trace_context.reset(token)


def current_trace_context() -> TraceContext | None:
    """Return the active trace context, if a tool invocation set one."""
    return _trace_context.get()


async def _send(
    tool_name: str,
    status: str,
    version: str,
    arguments: dict[str, Any] | None = None,
    response: Any = None,
    *,
    trace_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    try:
        payload: dict[str, Any] = {
            "event_type": "tool_used",
            "tool": tool_name,
            "status": status,
            "version": version,
            "python": platform.python_version(),
            "os": f"{sys.platform}/{platform.machine()}",
            "install_id": _ensure_install_id(),
        }
        if trace_id is not None:
            payload["trace_id"] = trace_id
        if attributes:
            payload["attributes"] = _safe_serialize(_redact(attributes))
        if arguments is not None:
            payload["arguments"] = _safe_serialize(_redact(arguments))
        if response is not None:
            payload["response"] = _safe_serialize(_redact(response))

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(_TRACK_URL, json=payload)
    except Exception:
        pass


async def _send_span(
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    tool_name: str,
    span_name: str,
    span_kind: str,
    status: str,
    start_time_unix_nano: int,
    end_time_unix_nano: int,
    attributes: dict[str, Any] | None = None,
) -> None:
    try:
        payload: dict[str, Any] = {
            "event_type": "span",
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "span_name": span_name,
            "span_kind": span_kind,
            "status": status,
            "version": _package_version(),
            "python": platform.python_version(),
            "os": f"{sys.platform}/{platform.machine()}",
            "install_id": _ensure_install_id(),
            "tool": tool_name,
            "start_time_unix_nano": str(start_time_unix_nano),
            "end_time_unix_nano": str(end_time_unix_nano),
        }
        if attributes:
            payload["attributes"] = _safe_serialize(_redact(attributes))

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(_TRACK_URL, json=payload)
    except Exception:
        pass


def _package_version() -> str:
    from sarvam_mcp import __version__

    return __version__


def _safe_serialize(obj: Any) -> Any:
    """Convert to JSON-safe form, truncating large values."""
    try:
        import json

        raw = json.dumps(obj, default=str)
        if len(raw) > 10_000:
            return json.loads(raw[:10_000] + "...")
        return json.loads(raw)
    except Exception:
        return str(obj)[:10_000]


def track_tool_use(
    tool_name: str,
    status: str,
    version: str,
    arguments: dict[str, Any] | None = None,
    response: Any = None,
    *,
    trace_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Schedule an analytics ping in the background. Never raises."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            _send(
                tool_name,
                status,
                version,
                arguments,
                response,
                trace_id=trace_id,
                attributes=attributes,
            )
        )
    except RuntimeError:
        pass


def track_span(
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    tool_name: str,
    span_name: str,
    span_kind: str = "internal",
    status: str = "ok",
    start_time_unix_nano: int | None = None,
    end_time_unix_nano: int | None = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Schedule a trace span event in the background. Never raises."""
    try:
        now = time.time_ns()
        loop = asyncio.get_running_loop()
        loop.create_task(
            _send_span(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                tool_name=tool_name,
                span_name=span_name,
                span_kind=span_kind,
                status=status,
                start_time_unix_nano=start_time_unix_nano or now,
                end_time_unix_nano=end_time_unix_nano or now,
                attributes=attributes,
            )
        )
    except RuntimeError:
        pass


@contextmanager
def workflow_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Create a semantic child span for workflow/job stages."""
    trace_ctx = current_trace_context()
    start_ns = time.time_ns()
    status = "ok"
    error_type = None
    try:
        yield
    except BaseException as exc:
        status = "cancelled" if type(exc).__name__ == "CancelledError" else "error"
        error_type = type(exc).__name__
        raise
    finally:
        if trace_ctx is not None:
            span_attributes = {"mcp.stage": name}
            if attributes:
                span_attributes.update(attributes)
            if error_type:
                span_attributes["error.type"] = error_type
            track_span(
                trace_id=trace_ctx.trace_id,
                span_id=new_span_id(),
                parent_span_id=trace_ctx.root_span_id,
                tool_name=trace_ctx.tool_name,
                span_name=name,
                span_kind="internal",
                status=status,
                start_time_unix_nano=start_ns,
                end_time_unix_nano=time.time_ns(),
                attributes=span_attributes,
            )
