"""The /text-to-speech request body must only carry parameters the model supports.

``pitch`` and ``loudness`` are bulbul:v2-only. bulbul:v3 (the default and only
currently-exposed model) does not support them, so they must not be sent.
``pace``, which v3 does support, must still be included.
"""

from __future__ import annotations

from sarvam_mcp.tools.tts import _speak_body

_COMMON = dict(
    text="नमस्ते",
    target_language_code="hi-IN",
    speaker="priya",
    speech_sample_rate=24000,
    pitch=0.5,
    pace=1.25,
    loudness=2.0,
    enable_preprocessing=True,
)


def test_v3_body_omits_pitch_and_loudness():
    body = _speak_body(model="bulbul:v3", **_COMMON)
    assert "pitch" not in body
    assert "loudness" not in body
    # Supported params are still present.
    assert body["pace"] == 1.25
    assert body["inputs"] == ["नमस्ते"]
    assert body["model"] == "bulbul:v3"
    assert body["speech_sample_rate"] == 24000


def test_non_v3_model_still_sends_pitch_and_loudness():
    # Future-proofing: a v2-style model keeps the full parameter set.
    body = _speak_body(model="bulbul:v2", **_COMMON)
    assert body["pitch"] == 0.5
    assert body["loudness"] == 2.0
