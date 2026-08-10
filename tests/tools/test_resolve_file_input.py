"""``resolve_file_input`` must close its temp file before unlinking it.

Regression test for the bug where an exception raised before ``tmp.close()``
(bad base64, an oversized payload, a failed download) left the handle open
when the ``finally`` block tried to unlink it. On POSIX that mostly just
leaks a descriptor; on Windows ``Path.unlink`` on an open file raises
``PermissionError``, which masks the real error entirely (see #59).
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import httpx
import pytest

from sarvam_mcp.tools import _common
from sarvam_mcp.tools._common import resolve_file_input


@pytest.fixture
def simulate_windows_unlink(monkeypatch):
    """Make ``Path.unlink`` behave like Windows: raise if the file is still open.

    ``tempfile.NamedTemporaryFile`` hands back a wrapper whose ``.close()`` we
    track; ``Path.unlink`` then raises ``PermissionError`` unless that wrapper
    was closed first — exactly what a real Windows filesystem does, and what
    let the original bug hide on macOS/Linux (where unlinking an open fd
    silently "succeeds").
    """
    real_new_temp_file = tempfile.NamedTemporaryFile
    state = {"closed": False}

    def tracking_factory(*args, **kwargs):
        tmp = real_new_temp_file(*args, **kwargs)
        real_close = tmp.close

        def tracking_close():
            state["closed"] = True
            real_close()

        tmp.close = tracking_close
        return tmp

    real_unlink = Path.unlink

    def windows_like_unlink(self, *args, **kwargs):
        if not state["closed"]:
            raise PermissionError(
                f"[WinError 32] The process cannot access the file because it is "
                f"being used by another process: '{self}'"
            )
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(_common.tempfile, "NamedTemporaryFile", tracking_factory)
    monkeypatch.setattr(Path, "unlink", windows_like_unlink)
    return state


async def test_bad_base64_raises_decode_error_not_permission_error(simulate_windows_unlink):
    with pytest.raises(Exception) as excinfo:
        async with resolve_file_input(file_base64="not-valid-base64!!!", filename="x.wav"):
            pass  # pragma: no cover - should never yield
    assert not isinstance(excinfo.value, PermissionError)


async def test_oversized_base64_raises_value_error_not_permission_error(simulate_windows_unlink):
    data = b"x" * 100
    encoded = base64.b64encode(data).decode()

    with pytest.raises(ValueError, match="exceeds"):
        async with resolve_file_input(file_base64=encoded, filename="x.bin", max_bytes=10):
            pass  # pragma: no cover - should never yield


async def test_failed_download_raises_http_error_not_permission_error(simulate_windows_unlink, httpx_mock):
    httpx_mock.add_response(url="https://example.invalid/file.wav", status_code=500)

    with pytest.raises(httpx.HTTPStatusError):
        async with resolve_file_input(file_url="https://example.invalid/file.wav", filename="x.wav"):
            pass  # pragma: no cover - should never yield


async def test_successful_base64_still_yields_and_cleans_up():
    data = b"hello world"
    encoded = base64.b64encode(data).decode()

    async with resolve_file_input(file_base64=encoded, filename="x.txt") as path:
        assert path.exists()
        assert path.read_bytes() == data

    # Cleaned up on exit, same as before the fix.
    assert not path.exists()
