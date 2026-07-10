"""TTS tool response helpers."""

from __future__ import annotations

from sarvam_mcp.audio import StoredAudio
from sarvam_mcp.tools.tts import _stored_audio_fields


def test_stored_audio_fields_preserves_resource_payload():
    stored = StoredAudio(
        file_path=None,
        resource_uri="sarvam://x.wav",
        base64_data="ZmFrZS13YXY=",
        mime_type="audio/wav",
        size_bytes=8,
    )

    assert _stored_audio_fields(stored) == {
        "file_path": None,
        "resource_uri": "sarvam://x.wav",
        "base64_data": "ZmFrZS13YXY=",
        "mime_type": "audio/wav",
        "size_bytes": 8,
    }
