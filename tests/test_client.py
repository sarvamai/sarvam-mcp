"""SarvamClient tests — auth header propagation, error mapping, observability."""

from __future__ import annotations

import httpx
import pytest

from sarvam_mcp.http import (
    SarvamAPIError,
    SarvamAuthError,
    SarvamClient,
    SarvamConnectionError,
    SarvamRateLimitError,
)
from sarvam_mcp.http.errors import SarvamBadRequestError


@pytest.fixture
async def client():
    c = SarvamClient("https://api.sarvam.ai")
    yield c
    await c.aclose()


async def test_auth_header_is_attached(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/translate",
        json={"translated_text": "ok"},
        headers={"x-request-id": "req_123"},
    )

    payload, metrics = await client.post_json("/translate", json_body={"input": "hi"})

    request = httpx_mock.get_request()
    assert request.headers["api-subscription-key"] == "sk_test_key_for_unit_tests_abcd"
    assert payload == {"translated_text": "ok"}
    assert metrics.request_id == "req_123"
    assert metrics.status_code == 200


async def test_401_maps_to_auth_error(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/translate",
        status_code=401,
        json={"error": "invalid token"},
    )
    with pytest.raises(SarvamAuthError) as exc_info:
        await client.post_json("/translate", json_body={"input": "x"})
    assert exc_info.value.status_code == 401


async def test_429_maps_to_rate_limit_with_retry_after(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/translate",
        status_code=429,
        headers={"retry-after": "12.5"},
        json={"error": "slow down"},
    )
    with pytest.raises(SarvamRateLimitError) as exc_info:
        await client.post_json("/translate", json_body={"input": "x"})
    assert exc_info.value.retry_after == 12.5


async def test_400_maps_to_bad_request(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/translate",
        status_code=400,
        json={"message": "missing source_language_code"},
    )
    with pytest.raises(SarvamBadRequestError) as exc_info:
        await client.post_json("/translate", json_body={})
    assert "missing" in str(exc_info.value)


async def test_5xx_retries_then_succeeds(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/translate",
        status_code=503,
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/translate",
        status_code=200,
        json={"translated_text": "ok"},
    )
    payload, _ = await client.post_json("/translate", json_body={"input": "x"})
    assert payload == {"translated_text": "ok"}
    assert len(httpx_mock.get_requests()) == 2


async def test_5xx_exhausts_retries(client, httpx_mock):
    # retry_async runs at most 3 attempts.
    for _ in range(3):
        httpx_mock.add_response(
            method="POST",
            url="https://api.sarvam.ai/translate",
            status_code=503,
        )
    with pytest.raises(SarvamAPIError) as exc_info:
        await client.post_json("/translate", json_body={"input": "x"})
    assert exc_info.value.status_code == 503


async def test_transport_error_maps_to_connection_error(client, httpx_mock):
    # A connection/DNS/timeout failure must surface as a typed error, not a
    # raw httpx exception leaking out of the client.
    for _ in range(3):  # retry_async runs at most 3 attempts.
        httpx_mock.add_exception(httpx.ConnectError("connection refused"))

    with pytest.raises(SarvamConnectionError) as exc_info:
        await client.post_json("/translate", json_body={"input": "x"})

    assert exc_info.value.status_code is None
    assert "ConnectError" in str(exc_info.value)
    # The originating httpx error is preserved on the chain.
    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)
    assert len(httpx_mock.get_requests()) == 3


async def test_connection_error_is_a_sarvam_api_error(client, httpx_mock):
    # Subclass of SarvamAPIError so existing `except SarvamAPIError` handlers
    # keep catching network failures.
    for _ in range(3):
        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))

    with pytest.raises(SarvamAPIError):
        await client.post_json("/translate", json_body={"input": "x"})


async def test_binary_response_returned_as_bytes(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/text-to-speech",
        content=b"RIFF....fake-wav",
        headers={"content-type": "audio/wav"},
    )
    payload, _ = await client.post_json("/text-to-speech", json_body={"text": "hi"})
    assert isinstance(payload, bytes)
    assert payload.startswith(b"RIFF")
