"""Tests for shared tool helpers in ``_common`` — currently ``resolve_file_input``."""

from __future__ import annotations

import tempfile

import httpx
import pytest

from sarvam_mcp.tools._common import resolve_file_input


@pytest.fixture
def capture_tempfiles(monkeypatch):
    """Capture every ``NamedTemporaryFile`` ``resolve_file_input`` opens."""
    created = []
    real = tempfile.NamedTemporaryFile

    def spy(*args, **kwargs):
        tmp = real(*args, **kwargs)
        created.append(tmp)
        return tmp

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy)
    return created


async def test_url_download_failure_closes_temp_file(capture_tempfiles, httpx_mock):
    """A non-2xx download must still close the temp file before cleanup.

    Otherwise the file descriptor leaks (POSIX) and ``tmp_path.unlink`` raises
    ``PermissionError`` on Windows, masking the original HTTP error.
    """
    httpx_mock.add_response(method="GET", url="https://files.example/missing.wav", status_code=404)

    with pytest.raises(httpx.HTTPStatusError):
        async with resolve_file_input(file_url="https://files.example/missing.wav", filename="missing.wav"):
            pass

    assert capture_tempfiles, "expected a temp file to have been created"
    assert capture_tempfiles[0].closed, "temp file was left open after a failed download"


async def test_url_download_over_size_limit_closes_temp_file(capture_tempfiles, httpx_mock):
    """Aborting mid-stream on the size limit must also close the temp file."""
    httpx_mock.add_response(method="GET", url="https://files.example/big.wav", content=b"x" * 64)

    with pytest.raises(ValueError):
        async with resolve_file_input(
            file_url="https://files.example/big.wav", filename="big.wav", max_bytes=16
        ):
            pass

    assert capture_tempfiles, "expected a temp file to have been created"
    assert capture_tempfiles[0].closed, "temp file was left open after exceeding the size limit"
