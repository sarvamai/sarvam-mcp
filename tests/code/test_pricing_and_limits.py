"""Docs-synced pricing + rate-limit tables and the tools that serve them."""

from __future__ import annotations

from fastmcp import Client

from sarvam_mcp.code import _data


def test_every_priced_service_has_rates():
    for key, entry in _data.PRICING.items():
        assert "unit" in entry, key
        assert "rates_inr_by_plan" in entry or "rates_inr" in entry, key


def test_key_prices_match_docs():
    p = _data.PRICING
    assert p["bulbul:v4-flash"]["rates_inr_by_plan"] == {"payg": 2.00, "pro": 1.85, "growth": 1.70}
    assert p["bulbul:v3"]["rates_inr_by_plan"]["payg"] == 3.00
    assert p["saaras:v4"]["rates_inr_by_plan"]["growth"] == 0.41
    assert p["dictate"]["rates_inr_by_plan"]["business"] == 0.40
    assert p["sarvam-105b"]["rates_inr"] == {"input": 10, "cached_input": 0.25, "output": 25}
    assert p["deepseekv4.1-flash-1017"]["rates_inr"]["output"] == 55  # cut 2026-11-07
    assert p["sarvam-prism"]["rates_inr"]["output"] == 0


def test_rate_limits_match_docs():
    r = _data.RATE_LIMITS
    assert (r["stt_rest"]["payg"], r["stt_rest"]["growth"]) == (60, 4000)
    assert r["llm_sarvam_105b"]["growth"] == 300
    assert r["doc_ai_extract"]["pages_per_request"] == 500
    assert r["voice_watermark_detect"]["all_plans"] == 5


def test_deprecated_models_not_priced():
    assert not set(_data.DEPRECATED_MODELS) & set(_data.PRICING)


async def test_pricing_tool_plan_filter():
    from sarvam_mcp.server import build_server

    async with Client(build_server()) as c:
        out = (
            await c.call_tool("sarvam_code_pricing", {"model": "bulbul:v4-flash", "plan": "pro"})
        ).data
        assert out["found"] and out["rate_inr"] == 1.85
        dep = (await c.call_tool("sarvam_code_pricing", {"model": "sarvam-30b"})).data
        assert dep["found"] is False and "sarvam-105b" in dep["deprecated"]
        lim = (await c.call_tool("sarvam_code_rate_limits", {"api": "tts_websocket"})).data
        assert lim["found"] and lim["unit"] == "concurrent" and lim["pro"] == 200
        none = (await c.call_tool("sarvam_code_rate_limits", {"api": "nope"})).data
        assert none["found"] is False
