"""Pure-logic helpers for ``sv_meet``: transcript rendering and summary parsing."""

from __future__ import annotations

from sarvam_mcp.workflows.meet import _parse_meeting_summary, _render_diarized_transcript


def test_render_falls_back_to_plain_transcript_when_entries_missing():
    text, turns = _render_diarized_transcript(None, "plain fallback transcript")
    assert text == "plain fallback transcript"
    assert turns == []


def test_render_falls_back_to_plain_transcript_when_entries_empty():
    text, turns = _render_diarized_transcript({"entries": []}, "plain fallback transcript")
    assert text == "plain fallback transcript"
    assert turns == []


def test_render_multi_speaker_with_timestamps():
    diarized = {
        "entries": [
            {
                "transcript": "Hello, how can I help you today?",
                "start_time_seconds": 0.01,
                "end_time_seconds": 2.5,
                "speaker_id": "0",
            },
            {
                "transcript": "I have a question.",
                "start_time_seconds": 2.8,
                "end_time_seconds": 4.2,
                "speaker_id": "1",
            },
        ]
    }
    text, turns = _render_diarized_transcript(diarized, "unused fallback")
    assert text == (
        "[0.0s–2.5s] Speaker 0: Hello, how can I help you today?\n[2.8s–4.2s] Speaker 1: I have a question."
    )
    assert turns == diarized["entries"]


def test_parse_valid_json():
    raw = (
        '{"summary": "Team agreed on the launch date.", '
        '"action_items": ["Ship by Friday"], '
        '"decisions": ["Launch on Friday"]}'
    )
    parsed = _parse_meeting_summary(raw)
    assert parsed == {
        "summary": "Team agreed on the launch date.",
        "action_items": ["Ship by Friday"],
        "decisions": ["Launch on Friday"],
    }


def test_parse_json_wrapped_in_code_fence():
    raw = '```json\n{"summary": "Short recap.", "action_items": [], "decisions": []}\n```'
    parsed = _parse_meeting_summary(raw)
    assert parsed == {"summary": "Short recap.", "action_items": [], "decisions": []}


def test_parse_malformed_json_falls_back_to_parse_warning():
    raw = "Sure, here's the summary: the team discussed the roadmap."
    parsed = _parse_meeting_summary(raw)
    assert parsed["summary"] == raw
    assert parsed["action_items"] == []
    assert parsed["decisions"] == []
    assert "parse_warning" in parsed


def test_parse_valid_but_non_dict_json_falls_back_to_parse_warning():
    raw = '["summary text", "not", "a", "dict"]'
    parsed = _parse_meeting_summary(raw)
    assert parsed["summary"] == raw
    assert parsed["action_items"] == []
    assert parsed["decisions"] == []
    assert "parse_warning" in parsed
