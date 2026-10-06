"""TTS model/speaker resolution and WebSocket config payload."""

import json

from sarvam_mcp.tools._common import DEFAULT_TTS_SPEAKERS, resolve_tts_speaker
from sarvam_mcp.tools.tts import _ws_config_payload


def test_default_speaker_follows_model():
    assert resolve_tts_speaker("bulbul:v3", None) == "shubh"
    assert resolve_tts_speaker("bulbul:v4-flash", None) == "shubh_enhi_ads"
    assert set(DEFAULT_TTS_SPEAKERS) == {"bulbul:v3", "bulbul:v4-flash"}


def test_explicit_speaker_wins():
    assert resolve_tts_speaker("bulbul:v4-flash", "simran_en_customer") == "simran_en_customer"


def test_ws_config_omits_unset_pitch_and_loudness():
    data = json.loads(_ws_config_payload(speaker="s", language_code="en-IN", pace=1.0))["data"]
    assert "pitch" not in data and "loudness" not in data


def test_ws_config_includes_pitch_and_loudness_when_set():
    data = json.loads(
        _ws_config_payload(speaker="s", language_code="en-IN", pace=1.0, pitch=0.2, loudness=1.5)
    )["data"]
    assert data["pitch"] == 0.2 and data["loudness"] == 1.5
