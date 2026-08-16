"""Audio output strategies — picked once at startup, injected into tools."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sarvam_mcp.audio.uris import build_resource_uri
from sarvam_mcp.config import OutputMode


@dataclass(frozen=True)
class StoredAudio:
    """The result of writing audio through a sink. Tools spread this into responses."""

    file_path: str | None
    resource_uri: str | None
    base64_data: str | None
    mime_type: str
    size_bytes: int


class AudioSink(Protocol):
    """Strategy for what to do with bytes emitted by a TTS/STT tool."""

    async def store(self, data: bytes, *, filename: str, mime_type: str) -> StoredAudio:
        ...


class FileSink:
    """Write to disk under ``base_path`` and return the file path."""

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path

    async def store(self, data: bytes, *, filename: str, mime_type: str) -> StoredAudio:
        self._base_path.mkdir(parents=True, exist_ok=True)
        base = self._base_path.resolve()
        path = (base / filename).resolve()
        if not path.is_relative_to(base):
            raise ValueError(f"filename escapes base path: {filename!r}")
        path.write_bytes(data)
        return StoredAudio(
            file_path=str(path),
            resource_uri=None,
            base64_data=None,
            mime_type=mime_type,
            size_bytes=len(data),
        )


class ResourceSink:
    """Return a base64-encoded resource — no disk I/O.

    Useful for containerized clients or sandboxed environments where the
    MCP server has no writable filesystem.
    """

    async def store(self, data: bytes, *, filename: str, mime_type: str) -> StoredAudio:
        return StoredAudio(
            file_path=None,
            resource_uri=build_resource_uri(filename),
            base64_data=base64.b64encode(data).decode("ascii"),
            mime_type=mime_type,
            size_bytes=len(data),
        )


class BothSink:
    """Write to disk *and* return as resource. Maximum flexibility."""

    def __init__(self, base_path: Path) -> None:
        self._file_sink = FileSink(base_path)
        self._resource_sink = ResourceSink()

    async def store(self, data: bytes, *, filename: str, mime_type: str) -> StoredAudio:
        file_result = await self._file_sink.store(data, filename=filename, mime_type=mime_type)
        resource_result = await self._resource_sink.store(
            data, filename=filename, mime_type=mime_type
        )
        return StoredAudio(
            file_path=file_result.file_path,
            resource_uri=resource_result.resource_uri,
            base64_data=resource_result.base64_data,
            mime_type=mime_type,
            size_bytes=len(data),
        )


def build_sink(mode: OutputMode, base_path: Path) -> AudioSink:
    """Construct the configured sink. Called once at server startup."""
    if mode == "files":
        return FileSink(base_path)
    if mode == "resources":
        return ResourceSink()
    if mode == "both":
        return BothSink(base_path)
    raise ValueError(f"Unknown output mode: {mode!r}")
