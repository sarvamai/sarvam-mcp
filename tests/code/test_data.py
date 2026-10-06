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
    # Matches docs.sarvam.ai; 'niharika' was rejected live on 2026-09-29.
    assert len(_data.V3_SPEAKERS) == 37


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


def test_v4_flash_roster_matches_live_api():
    # Matches docs.sarvam.ai; the 2 live Assamese personas are intentionally excluded.
    roster = _data.SPEAKERS_BY_MODEL["bulbul:v4-flash"]
    assert len(roster) == 222 and len(set(roster)) == 222
    assert "shubh_enhi_ads" in roster  # documented default
    assert "simran_en_customer" in roster
    assert not set(roster) & set(_data.V3_SPEAKERS)  # v3 names are rejected on v4-flash


def test_v4_flash_roster_reflects_2026_10_06_renames():
    roster = set(_data.SPEAKERS_BY_MODEL["bulbul:v4-flash"])
    assert {"arnab_bn_conversation", "aravind_ta_ads", "aravind_ta_suspense"} <= roster
    assert not roster & {"bappa_bn_conversation", "vetri_ta_ads", "vetri_ta_suspense"}
    assert not any("_as_" in s for s in roster)  # Assamese voices need Sarvam to enable them
