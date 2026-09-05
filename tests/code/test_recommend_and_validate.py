"""Recommendation heuristics + request validator."""

from __future__ import annotations

from sarvam_mcp.code.snippets import _recommend, _validate

# ---- recommend ------------------------------------------------------------


def test_recommend_picks_saaras_for_audio_to_english():
    result = _recommend("transcribe Hindi voicemails into English text")
    assert result["matched"]
    assert result["recommended_model"] == "saaras:v4"
    assert result["endpoint"] == "/speech-to-text"
    assert result["mode"] == "translate"


def test_recommend_picks_saaras_for_indic_transcription():
    result = _recommend("transcribe Tamil customer-support calls")
    assert result["matched"]
    assert result["recommended_model"] == "saaras:v4"
    assert result["language_code"] == "ta-IN"
    assert result["mode"] == "transcribe"


def test_recommend_picks_bulbul_for_tts():
    result = _recommend("synthesize Hindi speech for our IVR")
    assert result["matched"]
    assert result["recommended_model"] == "bulbul:v3"
    assert result["language_code"] == "hi-IN"


def test_recommend_picks_sarvam_translate_for_22_langs():
    result = _recommend("translate strings into Sindhi and Maithili and Bodo")
    assert result["matched"]
    assert result["recommended_model"] == "sarvam-translate:v1"


def test_recommend_picks_105b_for_reasoning_signal():
    result = _recommend("build a complex reasoning agent that uses tool use")
    assert result["matched"]
    assert result["recommended_model"] == "sarvam-105b"


def test_recommend_returns_unmatched_for_unrelated():
    result = _recommend("sort my photos by date")
    assert result["matched"] is False


def test_recommend_long_audio_points_at_job_v1_not_job_init():
    result = _recommend("transcribe a long Hindi meeting recording")
    assert result["matched"]
    taught = " ".join(str(value) for value in result.values())
    assert "/speech-to-text/job/v1" in taught
    assert "/speech-to-text/job/init" not in taught


# ---- validate -------------------------------------------------------------


def test_validate_tts_v3_with_v2_speaker_flags_error():
    issues = _validate(
        "/text-to-speech",
        {
            "inputs": ["hi"],
            "target_language_code": "hi-IN",
            "model": "bulbul:v3",
            "speaker": "anushka",  # v2-only speaker
        },
    )
    speaker_errors = [i for i in issues if i["field"] == "speaker"]
    assert speaker_errors and speaker_errors[0]["severity"] == "error"


def test_validate_tts_v3_with_v3_speaker_passes():
    issues = _validate(
        "/text-to-speech",
        {
            "inputs": ["hi"],
            "target_language_code": "hi-IN",
            "model": "bulbul:v3",
            "speaker": "priya",
        },
    )
    assert not [i for i in issues if i["severity"] == "error"]


def test_validate_stt_rejects_invalid_stt_model():
    issues = _validate("/speech-to-text", {"model": "stt-legacy-99"})
    assert [i for i in issues if i["field"] == "model"]
    assert any("saaras:v4" in (i.get("fix", "") + i.get("message", "")) for i in issues)


def test_validate_translate_rejects_unknown_language():
    issues = _validate(
        "/translate",
        {
            "input": "hello",
            "source_language_code": "en-IN",
            "target_language_code": "xx-XX",  # bogus
            "model": "mayura:v1",
        },
    )
    lang_errors = [i for i in issues if i["field"] == "target_language_code"]
    assert lang_errors


def test_validate_text_analytics_requires_typed_questions():
    issues = _validate(
        "/text-analytics",
        {
            "text": "Sarvam is an Indian AI company.",
            "questions": [{"id": "q1", "text": "Where is Sarvam based?"}],  # missing 'type'
        },
    )
    assert any("type" in i["field"] for i in issues)


def test_validate_clean_request_returns_no_errors():
    issues = _validate(
        "/v1/chat/completions",
        {
            "model": "sarvam-105b",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.5,
        },
    )
    assert not [i for i in issues if i["severity"] == "error"]
