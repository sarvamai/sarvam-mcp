"""Shared tool-helper tests."""

from __future__ import annotations

import httpx
import pytest

from sarvam_mcp.tools._common import resolve_file_input


async def test_resolve_file_input_url_preserves_http_error(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://example.test/missing.wav",
        status_code=404,
        text="not found",
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        async with resolve_file_input(
            file_url="https://example.test/missing.wav",
            filename="missing.wav",
        ):
            raise AssertionError("context body should not run")

    assert exc_info.value.response.status_code == 404


async def test_resolve_file_input_url_preserves_size_limit_error(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://example.test/too-large.wav",
        content=b"abcdef",
    )

    with pytest.raises(ValueError, match="Downloaded file exceeds"):
        async with resolve_file_input(
            file_url="https://example.test/too-large.wav",
            filename="too-large.wav",
            max_bytes=3,
        ):
            raise AssertionError("context body should not run")
