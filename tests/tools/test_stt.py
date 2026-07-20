"""Unit tests for the /download-files consistency-lag retry in stt_batch_transcribe."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sarvam_mcp.http.errors import SarvamBadRequestError
from sarvam_mcp.observability import CallMetrics, ToolMetrics
from sarvam_mcp.tools.stt import _fetch_download_urls


class _FakeClient:
    def __init__(self, post_json):
        self.post_json = post_json


class _FakeServerContext:
    def __init__(self, post_json):
        self.client = _FakeClient(post_json)


async def test_retries_once_on_not_yet_completed_then_succeeds(monkeypatch):
    monkeypatch.setattr("sarvam_mcp.tools.stt.asyncio.sleep", AsyncMock())

    not_ready = SarvamBadRequestError("Job abc123 is not in COMPLETED state. Current state: Pending")
    success_body = {"download_urls": {"0.json": {"file_url": "https://example.com/0.json"}}}
    post_json = AsyncMock(side_effect=[not_ready, (success_body, CallMetrics(request_id="r1"))])
    sc = _FakeServerContext(post_json)
    metrics = ToolMetrics(latency_ms=0.0)

    result = await _fetch_download_urls(sc, "abc123", ["0.json"], metrics)

    assert result == success_body["download_urls"]
    assert post_json.call_count == 2
    assert metrics.request_ids == ["r1"]


async def test_gives_up_after_max_attempts_with_clear_error(monkeypatch):
    monkeypatch.setattr("sarvam_mcp.tools.stt.asyncio.sleep", AsyncMock())

    always_not_ready = SarvamBadRequestError("Job abc123 is not in COMPLETED state. Current state: Pending")
    post_json = AsyncMock(side_effect=always_not_ready)
    sc = _FakeServerContext(post_json)
    metrics = ToolMetrics(latency_ms=0.0)

    with pytest.raises(RuntimeError, match="abc123"):
        await _fetch_download_urls(sc, "abc123", ["0.json"], metrics)

    assert post_json.call_count == 3  # DOWNLOAD_READY_ATTEMPTS


async def test_does_not_retry_a_different_bad_request_error(monkeypatch):
    monkeypatch.setattr("sarvam_mcp.tools.stt.asyncio.sleep", AsyncMock())

    unrelated_error = SarvamBadRequestError("job_id is required")
    post_json = AsyncMock(side_effect=unrelated_error)
    sc = _FakeServerContext(post_json)
    metrics = ToolMetrics(latency_ms=0.0)

    with pytest.raises(RuntimeError):
        await _fetch_download_urls(sc, "abc123", ["0.json"], metrics)

    assert post_json.call_count == 1
