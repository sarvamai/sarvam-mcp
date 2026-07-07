"""Shared tool helper tests."""

from __future__ import annotations

import base64

import pytest

from sarvam_mcp.tools._common import resolve_file_input


async def test_resolve_file_input_rejects_oversized_local_file(tmp_path):
    path = tmp_path / "large.wav"
    path.write_bytes(b"12345")

    with pytest.raises(ValueError, match="exceeds 4 byte limit"):
        async with resolve_file_input(file_path=str(path), max_bytes=4):
            pass


async def test_resolve_file_input_allows_local_file_at_limit(tmp_path):
    path = tmp_path / "small.wav"
    path.write_bytes(b"1234")

    async with resolve_file_input(file_path=str(path), max_bytes=4) as resolved:
        assert resolved == path


async def test_resolve_file_input_rejects_oversized_base64():
    encoded = base64.b64encode(b"12345").decode("ascii")

    with pytest.raises(ValueError, match="exceeds 4 byte limit"):
        async with resolve_file_input(file_base64=encoded, filename="large.wav", max_bytes=4):
            pass
