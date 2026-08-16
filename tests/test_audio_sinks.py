"""Audio sink tests."""

from __future__ import annotations

import base64

import pytest

from sarvam_mcp.audio import (
    BothSink,
    FileSink,
    ResourceSink,
    build_sink,
    parse_resource_uri,
)
from sarvam_mcp.audio.uris import build_resource_uri

SAMPLE = b"\x00\x01\x02fake-wav-bytes"


async def test_file_sink_writes_to_disk(tmp_base_path):
    sink = FileSink(tmp_base_path)
    result = await sink.store(SAMPLE, filename="x.wav", mime_type="audio/wav")

    assert result.file_path is not None
    assert result.resource_uri is None
    assert result.base64_data is None
    assert result.size_bytes == len(SAMPLE)
    written = (tmp_base_path / "x.wav").read_bytes()
    assert written == SAMPLE


async def test_resource_sink_returns_base64_no_disk(tmp_base_path):
    sink = ResourceSink()
    result = await sink.store(SAMPLE, filename="x.wav", mime_type="audio/wav")

    assert result.file_path is None
    assert result.resource_uri == "sarvam://x.wav"
    assert result.base64_data is not None
    assert base64.b64decode(result.base64_data) == SAMPLE
    assert not tmp_base_path.exists()  # ResourceSink never touches disk


async def test_both_sink_writes_and_returns_resource(tmp_base_path):
    sink = BothSink(tmp_base_path)
    result = await sink.store(SAMPLE, filename="x.wav", mime_type="audio/wav")

    assert result.file_path is not None
    assert result.resource_uri == "sarvam://x.wav"
    assert result.base64_data is not None
    assert (tmp_base_path / "x.wav").read_bytes() == SAMPLE


async def test_file_sink_rejects_traversal_filename(tmp_base_path):
    sink = FileSink(tmp_base_path)
    with pytest.raises(ValueError, match="escapes base path"):
        await sink.store(SAMPLE, filename="../escape.wav", mime_type="audio/wav")
    assert not (tmp_base_path.parent / "escape.wav").exists()


async def test_file_sink_rejects_absolute_filename(tmp_base_path, tmp_path):
    sink = FileSink(tmp_base_path)
    outside = tmp_path / "outside.wav"
    with pytest.raises(ValueError, match="escapes base path"):
        await sink.store(SAMPLE, filename=str(outside), mime_type="audio/wav")
    assert not outside.exists()


async def test_file_sink_allows_plain_filename_after_guard(tmp_base_path):
    sink = FileSink(tmp_base_path)
    result = await sink.store(SAMPLE, filename="ok.wav", mime_type="audio/wav")
    assert result.file_path == str((tmp_base_path / "ok.wav").resolve())


def test_build_sink_dispatch(tmp_base_path):
    assert isinstance(build_sink("files", tmp_base_path), FileSink)
    assert isinstance(build_sink("resources", tmp_base_path), ResourceSink)
    assert isinstance(build_sink("both", tmp_base_path), BothSink)
    with pytest.raises(ValueError):
        build_sink("nonsense", tmp_base_path)  # type: ignore[arg-type]


def test_resource_uri_round_trip():
    assert parse_resource_uri(build_resource_uri("hello.wav")) == "hello.wav"
    # Filenames with spaces/unicode survive the round trip.
    assert parse_resource_uri(build_resource_uri("नमस्ते audio.wav")) == "नमस्ते audio.wav"


def test_parse_resource_uri_rejects_other_schemes():
    with pytest.raises(ValueError):
        parse_resource_uri("file:///tmp/x.wav")
    with pytest.raises(ValueError):
        parse_resource_uri("sarvam://")
