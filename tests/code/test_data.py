"""Sanity checks on the hard-coded reference data."""

from __future__ import annotations

from sarvam_mcp.code import _data
from sarvam_mcp.tools.stt import STT_JOB_BASE

_OBSOLETE_BATCH_STT_PATH = "/speech-to-text/job/init"


def test_all_languages_have_required_fields():
    assert len(_data.ALL_LANGUAGES) == 23
    for lang in _data.ALL_LANGUAGES:
        assert {"code", "name", "script"} <= lang.keys()
        assert lang["code"].endswith("-IN")


def test_tts_languages_subset_of_all():
    tts_codes = {lang["code"] for lang in _data.LANGUAGES_BY_API["tts"]}
    all_codes = {lang["code"] for lang in _data.ALL_LANGUAGES}
    assert tts_codes <= all_codes
    assert len(tts_codes) == 11  # TTS covers 11 langs.


def test_v3_speakers_count_matches_live_api():
    # Discovered 2026-04-27 by triggering the API's validation error.
    assert len(_data.V3_SPEAKERS) == 38


def test_default_speaker_priya_is_v3():
    assert "priya" in _data.V3_SPEAKERS


def test_pricing_table_covers_every_model_in_reference():
    referenced_models: set[str] = set()
    for _endpoint, ref in _data.API_REFERENCE.items():
        if model_str := ref.get("model"):
            for chunk in model_str.split(","):
                # Pull bare model ids out of the human-readable list.
                for word in chunk.split():
                    if ":" in word or word in {"sarvam-105b"}:
                        referenced_models.add(word.strip(",.()"))
    # Every referenced model must appear in PRICING.
    missing = referenced_models - _data.PRICING.keys()
    assert not missing, f"Pricing entries missing for: {missing}"


def test_batch_stt_reference_uses_runtime_job_v1_path():
    # Builder tables must document the same create-job path the runtime tool calls.
    assert STT_JOB_BASE == "/speech-to-text/job/v1"
    job_keys = [key for key in _data.API_REFERENCE if "job" in key]
    assert STT_JOB_BASE in _data.API_REFERENCE, (
        f"{STT_JOB_BASE!r} is not a key in API_REFERENCE; job keys present: {job_keys}"
    )
    assert _OBSOLETE_BATCH_STT_PATH not in _data.API_REFERENCE, (
        f"{_OBSOLETE_BATCH_STT_PATH!r} must not remain as the batch-STT reference key"
    )


def test_batch_stt_reference_describes_job_parameters_create_shape():
    # Create-job is POST {job_parameters} → job_id. SAS URLs come from a later
    # /upload-files call, not from the create response.
    ref = _data.API_REFERENCE[STT_JOB_BASE]
    request_body = ref.get("request_body") or {}
    response = ref.get("response") or {}

    assert ref.get("method") == "POST"
    assert "job_parameters" in request_body
    assert "job_id" in response
    assert "input_storage_path" not in response
    assert "output_storage_path" not in response

