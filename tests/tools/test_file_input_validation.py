"""Validation tests for remote file inputs."""

from __future__ import annotations

import base64

import pytest

from sarvam_mcp.tools import _common
from sarvam_mcp.tools._common import resolve_file_input


@pytest.mark.parametrize(
    "encoded",
    [
        "!!!!",
        "aGVsbG8=!!!!",
        "a===",
    ],
)
async def test_resolve_file_input_rejects_malformed_base64(encoded: str) -> None:
    with pytest.raises(ValueError, match="Invalid base64 file data"):
        async with resolve_file_input(file_base64=encoded, filename="audio.wav"):
            pass


async def test_resolve_file_input_accepts_valid_base64() -> None:
    content = b"valid audio bytes"
    encoded = base64.b64encode(content).decode("ascii")

    async with resolve_file_input(file_base64=encoded, filename="audio.wav") as path:
        assert path.suffix == ".wav"
        assert path.read_bytes() == content

    assert not path.exists()


async def test_resolve_file_input_validates_before_creating_temp_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("temporary file created for invalid base64")

    monkeypatch.setattr(_common.tempfile, "NamedTemporaryFile", fail_if_called)

    with pytest.raises(ValueError, match="Invalid base64 file data"):
        async with resolve_file_input(file_base64="!!!!", filename="audio.wav"):
            pass
