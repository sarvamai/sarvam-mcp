"""Shared helpers for composite workflows.

These wrap the raw HTTP calls so workflow modules don't repeat the
multipart/JSON plumbing that lives in ``tools/*.py``. Keep them small —
they exist to compose, not to reimplement.
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from pathlib import Path
from typing import Any

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import StoredAudio
from sarvam_mcp.observability import CallMetrics, ToolMetrics
from sarvam_mcp.tools._common import SarvamLLM


def _audio_mime(path: Path) -> str:
    return {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
    }.get(path.suffix.lower().lstrip("."), "application/octet-stream")


async def stt_transcribe(
    sc: ServerContext,
    audio_path: Path,
    *,
    language_code: str = "unknown",
    model: str = "saaras:v3",
    mode: str = "transcribe",
    metrics: ToolMetrics | None = None,
) -> tuple[str, str | None]:
    """Run STT, returning (transcript, detected_language)."""
    audio_bytes = await asyncio.to_thread(audio_path.read_bytes)
    files = {"file": (audio_path.name, audio_bytes, _audio_mime(audio_path))}
    data: dict[str, Any] = {
        "model": model,
        "language_code": language_code,
        "with_timestamps": "false",
    }
    if model == "saaras:v3":
        data["mode"] = mode
    body, call = await sc.client.post_multipart("/speech-to-text", data=data, files=files)
    if metrics is not None:
        metrics.merge(call)
    return body.get("transcript", ""), body.get("language_code")


async def translate_text(
    sc: ServerContext,
    text: str,
    *,
    source_language_code: str,
    target_language_code: str,
    model: str = "mayura:v1",
    mode: str = "formal",
    metrics: ToolMetrics | None = None,
) -> str:
    """Translate ``text`` and return the translated string."""
    # Upstream /translate accepts "auto", not "unknown".
    src = "auto" if source_language_code == "unknown" else source_language_code
    body_req: dict[str, Any] = {
        "input": text,
        "source_language_code": src,
        "target_language_code": target_language_code,
        "model": model,
        "numerals_format": "international",
    }
    if model == "mayura:v1":
        body_req["mode"] = mode
    body, call = await sc.client.post_json("/translate", json_body=body_req)
    if metrics is not None:
        metrics.merge(call)
    return body.get("translated_text", "")


async def tts_synthesize(
    sc: ServerContext,
    text: str,
    *,
    target_language_code: str,
    speaker: str = "priya",
    speech_sample_rate: int = 24000,
    model: str = "bulbul:v3",
    filename_prefix: str = "sv-out",
    metrics: ToolMetrics | None = None,
) -> StoredAudio:
    """Run TTS and persist via the configured audio sink."""
    body, call = await sc.client.post_json(
        "/text-to-speech",
        json_body={
            "inputs": [text],
            "target_language_code": target_language_code,
            "speaker": speaker,
            "speech_sample_rate": speech_sample_rate,
            "model": model,
            "enable_preprocessing": True,
        },
    )
    if metrics is not None:
        metrics.merge(call)
    audios = body.get("audios") or []
    if not audios:
        raise RuntimeError(f"TTS returned no audio. Raw: {body!r}")
    wav = base64.b64decode(audios[0])
    filename = f"{filename_prefix}-{uuid.uuid4().hex[:8]}.wav"
    return await sc.audio_sink.store(wav, filename=filename, mime_type="audio/wav")


async def llm_complete(
    sc: ServerContext,
    messages: list[dict[str, Any]],
    *,
    model: SarvamLLM = "sarvam-30b",
    temperature: float = 0.4,
    max_tokens: int = 600,
    metrics: ToolMetrics | None = None,
) -> str:
    """Run a chat completion and return the assistant text."""
    body, call = await sc.client.post_json(
        "/v1/chat/completions",
        json_body={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    if metrics is not None:
        metrics.merge(call)
    choice = (body.get("choices") or [{}])[0]
    return ((choice.get("message") or {}).get("content") or "").strip()


def merge(metrics: ToolMetrics, call: CallMetrics) -> None:
    """Convenience re-export so workflow modules don't import observability directly."""
    metrics.merge(call)
