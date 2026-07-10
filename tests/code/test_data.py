"""Sanity checks on the hard-coded reference data."""

from __future__ import annotations

from sarvam_mcp.code import _data


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


def test_pronunciation_reference_matches_runtime_delete_shape():
    # The runtime delete tool passes the id as a query param
    # (?dict_id=), not a path segment. The reference note must not tell
    # code-gen agents to use the path form.
    note = _data.API_REFERENCE["/text-to-speech/pronunciation-dictionary"]["notes"]
    assert "dict_id" in note
    assert "DELETE /{id}" not in note


def test_pricing_table_covers_every_model_in_reference():
    referenced_models: set[str] = set()
    for _endpoint, ref in _data.API_REFERENCE.items():
        if model_str := ref.get("model"):
            for chunk in model_str.split(","):
                # Pull bare model ids out of the human-readable list.
                for word in chunk.split():
                    if ":" in word or word in {"sarvam-30b", "sarvam-105b"}:
                        referenced_models.add(word.strip(",.()"))
    # Every referenced model must appear in PRICING.
    missing = referenced_models - _data.PRICING.keys()
    assert not missing, f"Pricing entries missing for: {missing}"
