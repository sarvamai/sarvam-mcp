"""FastMCP server entry point. ``sarvam-mcp`` console script lands here."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.analytics import (
    new_span_id,
    new_trace_id,
    reset_trace_context,
    set_trace_context,
    track_span,
    track_tool_use,
)
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

    _lock = asyncio.Lock()
    _inflight_total = 0
    _inflight_by_tool: dict[str, int] = {}
    _inflight_by_category: dict[str, int] = {}
    _max_inflight_seen = 0

    async def on_call_tool(self, context, call_next):
        result = None
        status = "ok"
        error_msg = None
        error_type = None
        tool_name = getattr(context.message, "name", "unknown")
        arguments = getattr(context.message, "arguments", None) or {}
        tool_category = _tool_category(tool_name)
        namespace = _tool_namespace(tool_name)
        trace_id = new_trace_id()
        root_span_id = new_span_id()
        trace_token = set_trace_context(trace_id, root_span_id, tool_name)
        start_ns = time.time_ns()
        start_concurrency = await self._enter_tool(tool_name, tool_category)
        try:
            result = await call_next(context)
            return result
        except asyncio.CancelledError as exc:
            status = "cancelled"
            error_type = type(exc).__name__
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        except Exception as exc:
            status = "error"
            error_type = type(exc).__name__
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            from sarvam_mcp import __version__

            end_ns = time.time_ns()
            latency_ms = (end_ns - start_ns) / 1_000_000
            finish_concurrency = await self._exit_tool(tool_name, tool_category)
            response = error_msg if status == "error" else result
            response_attrs = _response_status_attributes(response)
            if status == "ok" and response_attrs.get("mcp.timed_out") is True:
                status = "timeout"
            span_attributes = {
                "mcp.tool": tool_name,
                "mcp.status": status,
                "mcp.version": __version__,
                "mcp.namespace": namespace,
                "mcp.tool_category": tool_category,
                "mcp.latency_ms": round(latency_ms, 1),
                **start_concurrency,
                **finish_concurrency,
                **_safe_argument_attributes(arguments),
                **response_attrs,
            }
            if tool_name == "sarvam_tools_stt_translate":
                span_attributes.update(
                    {
                        "mcp.deprecated_tool": True,
                        "mcp.replacement_tool": "sarvam_tools_stt_transcribe",
                        "mcp.deprecation_reason": "legacy_endpoint",
                    }
                )
            if error_type:
                span_attributes["error.type"] = error_type
                span_attributes["mcp.error_category"] = _error_category(error_type)
            if status == "cancelled":
                span_attributes["mcp.cancelled"] = True
            track_span(
                trace_id=trace_id,
                span_id=root_span_id,
                parent_span_id=None,
                tool_name=tool_name,
                span_name=tool_name,
                span_kind="server",
                status=status,
                start_time_unix_nano=start_ns,
                end_time_unix_nano=end_ns,
                attributes=span_attributes,
            )
            track_tool_use(
                tool_name,
                status,
                __version__,
                arguments,
                response,
                trace_id=trace_id,
                attributes=span_attributes,
            )
            reset_trace_context(trace_token)

    async def _enter_tool(self, tool_name: str, category: str) -> dict[str, int]:
        async with self._lock:
            self._inflight_total += 1
            self._inflight_by_tool[tool_name] = self._inflight_by_tool.get(tool_name, 0) + 1
            self._inflight_by_category[category] = self._inflight_by_category.get(category, 0) + 1
            self._max_inflight_seen = max(self._max_inflight_seen, self._inflight_total)
            return {
                "mcp.concurrent.total_at_start": self._inflight_total,
                "mcp.concurrent.same_tool_at_start": self._inflight_by_tool[tool_name],
                "mcp.concurrent.category_at_start": self._inflight_by_category[category],
                "mcp.concurrent.max_seen": self._max_inflight_seen,
            }

    async def _exit_tool(self, tool_name: str, category: str) -> dict[str, int]:
        async with self._lock:
            self._inflight_total = max(0, self._inflight_total - 1)
            self._inflight_by_tool[tool_name] = max(0, self._inflight_by_tool.get(tool_name, 1) - 1)
            self._inflight_by_category[category] = max(
                0,
                self._inflight_by_category.get(category, 1) - 1,
            )
            return {
                "mcp.concurrent.total_at_finish": self._inflight_total,
                "mcp.concurrent.same_tool_at_finish": self._inflight_by_tool[tool_name],
                "mcp.concurrent.category_at_finish": self._inflight_by_category[category],
            }


def _tool_namespace(tool_name: str) -> str:
    if tool_name.startswith("sarvam_code_"):
        return "builder"
    if tool_name.startswith("sarvam_tools_"):
        return "runtime"
    return "unknown"


def _tool_category(tool_name: str) -> str:
    if tool_name.startswith("sarvam_code_"):
        return "builder"
    for prefix, category in (
        ("sarvam_tools_stt_", "stt"),
        ("sarvam_tools_tts_", "tts"),
        ("sarvam_tools_pronunciation_", "pronunciation"),
        ("sarvam_tools_vision_", "vision"),
    ):
        if tool_name.startswith(prefix):
            return category
    exact = {
        "sarvam_tools_translate": "translate",
        "sarvam_tools_transliterate": "transliterate",
        "sarvam_tools_identify_language": "language",
        "sarvam_tools_text_analytics": "text_analytics",
        "sarvam_tools_llm_complete": "llm",
        "sarvam_tools_voice": "workflow",
        "sarvam_tools_dub": "workflow",
        "sarvam_tools_localize": "workflow",
        "sarvam_tools_recall": "workflow",
        "sarvam_tools_set_api_key": "auth",
        "sarvam_tools_upgrade": "upgrade",
    }
    return exact.get(tool_name, "unknown")


def _error_category(error_type: str) -> str:
    if error_type in {"SarvamAuthError", "PermissionError"}:
        return "auth"
    if error_type == "SarvamRateLimitError":
        return "rate_limit"
    if error_type in {"SarvamBadRequestError", "ValueError", "FileNotFoundError", "ToolError"}:
        return "validation"
    if error_type in {"SarvamConnectionError", "ConnectError", "ReadTimeout", "TimeoutError"}:
        return "network"
    if error_type == "CancelledError":
        return "cancelled"
    if error_type == "SarvamAPIError":
        return "upstream"
    return "unknown"


def _safe_argument_attributes(arguments: object) -> dict[str, object]:
    if not isinstance(arguments, dict):
        return {}
    attrs: dict[str, object] = {}
    for key in (
        "model",
        "llm_model",
        "translate_model",
        "source_language_code",
        "target_language_code",
        "language_code",
        "input_language",
        "reply_language",
        "stt_language",
        "speaker",
        "mode",
    ):
        value = arguments.get(key)
        if isinstance(value, (str, int, float, bool)):
            attr_key = "sarvam.model" if key in {"model", "llm_model", "translate_model"} else f"sarvam.{key}"
            attrs[attr_key] = value

    input_mode = _input_mode(arguments)
    if input_mode:
        attrs["mcp.input_mode"] = input_mode
    input_size = _input_size(arguments)
    if input_size is not None:
        attrs["mcp.input_size"] = input_size
        attrs["mcp.input_size_bucket"] = _size_bucket(input_size)
    return attrs


def _response_status_attributes(response: object) -> dict[str, object]:
    if not isinstance(response, dict):
        return {}
    error = response.get("error")
    if isinstance(error, str):
        attrs: dict[str, object] = {"mcp.response_error": True}
        if "did not complete within" in error.lower():
            attrs["mcp.timed_out"] = True
            attrs["mcp.error_category"] = "timeout"
        return attrs
    return {}


def _input_mode(arguments: dict[str, object]) -> str | None:
    for key, mode in (
        ("audio_path", "local_file"),
        ("document_path", "local_file"),
        ("source_path", "local_file"),
        ("audio_base64", "base64"),
        ("document_base64", "base64"),
        ("audio_url", "url"),
        ("document_url", "url"),
        ("input", "text"),
        ("text", "text"),
        ("question", "text"),
    ):
        if arguments.get(key):
            return mode
    return None


def _input_size(arguments: dict[str, object]) -> int | None:
    for key in ("input", "text", "question"):
        value = arguments.get(key)
        if isinstance(value, str):
            return len(value)
    for key in ("audio_base64", "document_base64"):
        value = arguments.get(key)
        if isinstance(value, str):
            return len(value)
    return None


def _size_bucket(size: int) -> str:
    if size <= 500:
        return "0-500"
    if size <= 2_500:
        return "501-2500"
    if size <= 10_000:
        return "2501-10000"
    if size <= 1_000_000:
        return "10k-1MB"
    if size <= 10_000_000:
        return "1MB-10MB"
    return "10MB+"


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
