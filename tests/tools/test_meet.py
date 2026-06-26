"""Unit tests for the sv_meet workflow helpers and the diarized STT helper."""

from __future__ import annotations

import pytest

from sarvam_mcp.workflows.meet import _extract_bullets, _parse_llm_sections, _render_transcript

# ---------------------------------------------------------------------------
# _render_transcript
# ---------------------------------------------------------------------------


def test_render_transcript_maps_speaker_ids():
    turns = [
        {"speaker": "SPEAKER_00", "transcript": "Good morning everyone."},
        {"speaker": "SPEAKER_01", "transcript": "Hi, let's get started."},
        {"speaker": "SPEAKER_00", "transcript": "Sure, agenda first."},
    ]
    labeled, normalized = _render_transcript(turns, "")

    assert labeled == (
        "Speaker 1: Good morning everyone.\nSpeaker 2: Hi, let's get started.\nSpeaker 1: Sure, agenda first."
    )
    assert normalized[0]["speaker"] == "Speaker 1"
    assert normalized[1]["speaker"] == "Speaker 2"
    assert normalized[2]["speaker"] == "Speaker 1"


def test_render_transcript_accepts_text_key():
    turns = [{"speaker": "SPEAKER_00", "text": "Hello."}]
    labeled, normalized = _render_transcript(turns, "")
    assert "Speaker 1: Hello." in labeled
    assert normalized[0]["text"] == "Hello."


def test_render_transcript_falls_back_when_no_turns():
    flat = "This is the flat transcript."
    labeled, normalized = _render_transcript([], flat)
    assert labeled == flat
    assert normalized == []


def test_render_transcript_skips_empty_text_turns():
    turns = [
        {"speaker": "SPEAKER_00", "transcript": ""},
        {"speaker": "SPEAKER_01", "transcript": "Actually here."},
    ]
    labeled, _ = _render_transcript(turns, "")
    assert "Speaker 1:" not in labeled
    assert "Speaker 2: Actually here." in labeled


# ---------------------------------------------------------------------------
# _parse_llm_sections
# ---------------------------------------------------------------------------


_FULL_LLM_OUTPUT = """\
## Summary
The team discussed Q3 targets and the product roadmap.

## Action Items
- Alice to send the updated spec by Friday
- Bob to schedule a follow-up with engineering

## Decisions
- Launch date moved to October 1
- Budget approved for the new infra
"""

_NONE_LLM_OUTPUT = """\
## Summary
A quick sync to align on priorities.

## Action Items
- None.

## Decisions
- None.
"""


def test_parse_llm_sections_full():
    summary, actions, decisions = _parse_llm_sections(_FULL_LLM_OUTPUT)
    assert "Q3 targets" in summary
    assert len(actions) == 2
    assert actions[0] == "Alice to send the updated spec by Friday"
    assert len(decisions) == 2
    assert decisions[0] == "Launch date moved to October 1"


def test_parse_llm_sections_none_placeholders():
    summary, actions, decisions = _parse_llm_sections(_NONE_LLM_OUTPUT)
    assert "quick sync" in summary
    assert actions == []
    assert decisions == []


def test_parse_llm_sections_missing_sections():
    # If the LLM omits sections entirely, return empty lists — not an error.
    summary, actions, decisions = _parse_llm_sections("## Summary\nJust a summary.")
    assert summary == "Just a summary."
    assert actions == []
    assert decisions == []


# ---------------------------------------------------------------------------
# _extract_bullets
# ---------------------------------------------------------------------------


def test_extract_bullets_handles_numbered_list():
    text = "1. First item\n2. Second item"
    assert _extract_bullets(text) == ["First item", "Second item"]


def test_extract_bullets_handles_mixed_formats():
    text = "- Dash item\n* Star item\n• Bullet item"
    assert _extract_bullets(text) == ["Dash item", "Star item", "Bullet item"]


# ---------------------------------------------------------------------------
# stt_transcribe_diarized — integration with httpx_mock
# ---------------------------------------------------------------------------


@pytest.fixture
async def server_ctx(tmp_path):
    """Minimal ServerContext for workflow helper tests."""
    from sarvam_mcp._registry import ServerContext
    from sarvam_mcp.audio.sinks import FileSink
    from sarvam_mcp.config import Config
    from sarvam_mcp.http import SarvamClient

    client = SarvamClient("https://api.sarvam.ai")
    config = Config()
    sink = FileSink(tmp_path / "out")
    sc = ServerContext(config=config, client=client, audio_sink=sink)
    yield sc
    await client.aclose()


async def test_stt_transcribe_diarized_happy_path(server_ctx, tmp_path, httpx_mock):
    from sarvam_mcp.workflows._helpers import stt_transcribe_diarized

    audio_file = tmp_path / "meeting.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

    diarized_turns = [
        {"speaker": "SPEAKER_00", "transcript": "Hello team.", "start": 0.0, "end": 2.0},
        {"speaker": "SPEAKER_01", "transcript": "Hi everyone.", "start": 2.5, "end": 4.5},
    ]

    # 1. Create job
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/speech-to-text/job/v1",
        json={"job_id": "job-abc"},
    )
    # 2. Register files
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/speech-to-text/job/v1/upload-files",
        json={
            "upload_urls": {
                "meeting.wav": {
                    "file_url": "https://blob.azure.example.com/upload?sas=token",
                    "file_metadata": {},
                }
            }
        },
    )
    # 3. Azure Blob PUT
    httpx_mock.add_response(
        method="PUT",
        url="https://blob.azure.example.com/upload?sas=token",
        status_code=201,
    )
    # 4. Start job
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/speech-to-text/job/v1/job-abc/start",
        json={"job_id": "job-abc"},
    )
    # 5. Status — Completed
    httpx_mock.add_response(
        method="GET",
        url="https://api.sarvam.ai/speech-to-text/job/v1/job-abc/status",
        json={
            "job_state": "Completed",
            "result": {
                "transcript": "Hello team. Hi everyone.",
                "diarized_transcript": diarized_turns,
                "language_code": "en-IN",
            },
        },
    )

    transcript, turns, lang = await stt_transcribe_diarized(server_ctx, audio_file)

    assert transcript == "Hello team. Hi everyone."
    assert lang == "en-IN"
    assert len(turns) == 2
    assert turns[0]["speaker"] == "SPEAKER_00"


async def test_stt_transcribe_diarized_no_upload_urls_raises(server_ctx, tmp_path, httpx_mock):
    from sarvam_mcp.workflows._helpers import stt_transcribe_diarized

    audio_file = tmp_path / "meeting.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/speech-to-text/job/v1",
        json={"job_id": "job-xyz"},
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/speech-to-text/job/v1/upload-files",
        json={"upload_urls": {}},
    )

    with pytest.raises(RuntimeError, match="No upload URLs"):
        await stt_transcribe_diarized(server_ctx, audio_file)
