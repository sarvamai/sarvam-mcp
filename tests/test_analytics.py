"""Analytics redaction — secrets must never reach the analytics endpoint."""

from __future__ import annotations

import sarvam_mcp.analytics as analytics
from sarvam_mcp.analytics import _redact, _send


def test_redact_masks_api_key():
    out = _redact({"api_key": "sk_live_secret", "text": "hello"})
    assert out == {"api_key": "***redacted***", "text": "hello"}


def test_redact_is_case_insensitive_and_nested():
    out = _redact(
        {
            "API_KEY": "sk_1",
            "nested": {"Authorization": "Bearer xyz", "keep": 1},
            "items": [{"token": "t"}, {"ok": True}],
        }
    )
    assert out["API_KEY"] == "***redacted***"
    assert out["nested"]["Authorization"] == "***redacted***"
    assert out["nested"]["keep"] == 1
    assert out["items"][0]["token"] == "***redacted***"
    assert out["items"][1]["ok"] is True


def test_redact_preserves_benign_keys():
    # `max_tokens` contains the substring "token" but is not a secret — exact
    # key matching must leave it untouched.
    payload = {"max_tokens": 600, "model": "sarvam-30b", "temperature": 0.7}
    assert _redact(payload) == payload


async def test_send_does_not_transmit_api_key(httpx_mock, monkeypatch):
    monkeypatch.setattr(analytics, "_install_id", "test-install-id")
    httpx_mock.add_response(
        method="POST",
        url="https://mcp.sarvam.ai/api/track",
        json={"ok": True},
    )

    await _send(
        "sarvam_tools_set_api_key",
        "ok",
        "0.2.4",
        {"api_key": "sk_live_SECRET_should_never_leave"},
        {"status": "saved"},
    )

    body = httpx_mock.get_request().content.decode()
    assert "sk_live_SECRET_should_never_leave" not in body
    assert "***redacted***" in body
