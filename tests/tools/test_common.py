"""resolve_file_input resource handling — regression tests for issue #59.

The helper writes URL/base64 inputs to a NamedTemporaryFile(delete=False).
Historically the branch's own ``tmp.close()`` was only reached on success, so
any failure (bad URL, oversize payload, HTTP error) left the handle open when
the ``finally`` block unlinked the path — a PermissionError on Windows that
masked the real error, and an unlinked-but-open fd until GC on POSIX.

These tests record every close/unlink of the temp file and assert the file is
always closed *before* it is unlinked, on failure paths as well as success.
"""

from __future__ import annotations

import base64
import pathlib
import tempfile
from collections.abc import Iterator

import httpx
import pytest

from sarvam_mcp.tools._common import resolve_file_input


@pytest.fixture
def temp_file_events(monkeypatch) -> Iterator[list[tuple[str, str]]]:
    """Ordered (event, path) log for the temp file resolve_file_input creates.

    Only events for files created by the patched NamedTemporaryFile are
    recorded, in the order they happen, so tests can compare ordering.
    """
    events: list[tuple[str, str]] = []
    tracked: set[str] = set()

    real_ntf = tempfile.NamedTemporaryFile

    def tracking_ntf(*args, **kwargs):
        f = real_ntf(*args, **kwargs)
        tracked.add(f.name)
        real_close = f.close

        def close():
            events.append(("close", f.name))
            real_close()

        f.close = close
        return f

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", tracking_ntf)

    real_unlink = pathlib.Path.unlink

    def tracking_unlink(self: pathlib.Path, missing_ok: bool = False):
        if str(self) in tracked:
            events.append(("unlink", str(self)))
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(pathlib.Path, "unlink", tracking_unlink)
    yield events


def assert_closed_before_unlink(events: list[tuple[str, str]]) -> None:
    """Every unlinked temp file must have been closed first."""
    assert events, "resolve_file_input never created a temp file"
    closed: set[str] = set()
    for kind, path in events:
        if kind == "close":
            closed.add(path)
        else:
            assert path in closed, f"{path} was unlinked while still open"


async def test_oversize_base64_closes_temp_file_before_unlink(
    temp_file_events: list[tuple[str, str]],
) -> None:
    with pytest.raises(ValueError, match="exceeds"):
        async with resolve_file_input(file_base64=base64.b64encode(b"x" * 100).decode(), max_bytes=10):
            raise AssertionError("size-limit failure should have raised before yield")

    assert_closed_before_unlink(temp_file_events)
    assert temp_file_events[-1] == ("unlink", temp_file_events[-1][1])


async def test_http_error_closes_temp_file_before_unlink(
    temp_file_events: list[tuple[str, str]], httpx_mock
) -> None:
    httpx_mock.add_response(url="https://example.com/audio.wav", status_code=404)

    with pytest.raises(httpx.HTTPStatusError):
        async with resolve_file_input(file_url="https://example.com/audio.wav"):
            raise AssertionError("HTTP failure should have raised before yield")

    assert_closed_before_unlink(temp_file_events)


async def test_oversize_download_closes_temp_file_before_unlink(
    temp_file_events: list[tuple[str, str]], httpx_mock
) -> None:
    httpx_mock.add_response(url="https://example.com/audio.wav", content=b"x" * 100)

    with pytest.raises(ValueError, match="exceeds"):
        async with resolve_file_input(file_url="https://example.com/audio.wav", max_bytes=10):
            raise AssertionError("size-limit failure should have raised before yield")

    assert_closed_before_unlink(temp_file_events)


async def test_base64_success_closes_temp_file_before_unlink(
    temp_file_events: list[tuple[str, str]],
) -> None:
    payload = base64.b64encode(b"hello").decode()
    async with resolve_file_input(file_base64=payload, filename="in.wav") as path:
        assert path.read_bytes() == b"hello"
    assert_closed_before_unlink(temp_file_events)
    assert not path.exists()


async def test_url_success_closes_temp_file_before_unlink(
    temp_file_events: list[tuple[str, str]], httpx_mock
) -> None:
    httpx_mock.add_response(url="https://example.com/audio.wav", content=b"hello")

    async with resolve_file_input(file_url="https://example.com/audio.wav") as path:
        assert path.read_bytes() == b"hello"
    assert_closed_before_unlink(temp_file_events)
    assert not path.exists()
