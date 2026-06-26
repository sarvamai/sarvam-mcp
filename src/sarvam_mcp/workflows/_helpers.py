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

import httpx

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
    with audio_path.open("rb") as fh:
        files = {"file": (audio_path.name, fh, _audio_mime(audio_path))}
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


_BATCH_JOB_BASE = "/speech-to-text/job/v1"
_BATCH_JOB_UPLOAD = f"{_BATCH_JOB_BASE}/upload-files"
_BATCH_MAX_POLLS = 90
_BATCH_POLL_INTERVAL = 2  # seconds


async def stt_transcribe_diarized(
    sc: ServerContext,
    audio_path: Path,
    *,
    language_code: str = "unknown",
    model: str = "saaras:v3",
    num_speakers: int | None = None,
    metrics: ToolMetrics | None = None,
    ctx: Any = None,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """Batch STT with diarization enabled.

    Returns (flat_transcript, diarized_turns, detected_language_code).
    ``diarized_turns`` is a list of per-speaker turn dicts from the API;
    empty list when the API does not return diarization data.
    """

    async def _info(msg: str) -> None:
        if ctx is not None:
            await ctx.info(msg)

    job_params: dict[str, Any] = {
        "model": model,
        "with_diarization": True,
    }
    if language_code != "unknown":
        job_params["language_code"] = language_code
    if num_speakers is not None:
        job_params["num_speakers"] = num_speakers

    await _info("Creating batch STT job…")
    create_resp, call = await sc.client.post_json(_BATCH_JOB_BASE, json_body={"job_parameters": job_params})
    if metrics is not None:
        metrics.merge(call)
    job_id = create_resp["job_id"]

    await _info(f"Registering audio file for job {job_id}…")
    upload_resp, call = await sc.client.post_json(
        _BATCH_JOB_UPLOAD,
        json_body={"job_id": job_id, "files": [audio_path.name]},
    )
    if metrics is not None:
        metrics.merge(call)
    upload_urls = upload_resp.get("upload_urls", {})
    if not upload_urls:
        raise RuntimeError(f"No upload URLs returned for job {job_id}")

    await _info("Uploading audio to Azure Blob…")
    file_details = next(iter(upload_urls.values()))
    presigned_url = file_details["file_url"]
    file_metadata = file_details.get("file_metadata") or {}
    extra_headers = {str(k): str(v) for k, v in file_metadata.items()}
    with audio_path.open("rb") as fh:
        blob_call = await sc.client.put_blob(
            presigned_url,
            fh.read(),
            content_type=_audio_mime(audio_path),
            extra_headers=extra_headers,
        )
    if metrics is not None:
        metrics.merge(blob_call)

    await _info("Starting batch processing…")
    _, call = await sc.client.post_json(
        f"{_BATCH_JOB_BASE}/{job_id}/start",
        json_body={"job_id": job_id, "job_parameters": job_params},
    )
    if metrics is not None:
        metrics.merge(call)

    await _info("Polling for completion…")
    terminal = {"Completed", "PartiallyCompleted", "Failed", "failed", "error"}
    status_resp: dict[str, Any] = {}
    for _ in range(_BATCH_MAX_POLLS):
        status_resp, call = await sc.client.get_json(f"{_BATCH_JOB_BASE}/{job_id}/status")
        if metrics is not None:
            metrics.merge(call)
        if status_resp.get("job_state", "") in terminal:
            break
        await asyncio.sleep(_BATCH_POLL_INTERVAL)

    result = status_resp.get("result") or {}
    transcript = result.get("transcript") or status_resp.get("transcript") or ""
    diarized: list[dict[str, Any]] = result.get("diarized_transcript") or []

    if not transcript and status_resp.get("download_urls"):
        dl_url = next(iter(status_resp["download_urls"].values()))["file_url"]
        await _info("Downloading transcript…")
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as dl:
            dl_resp = await dl.get(dl_url)
        if dl_resp.is_success:
            dl_body = dl_resp.json()
            transcript = dl_body.get("transcript", "")
            diarized = dl_body.get("diarized_transcript") or []
            result = dl_body

    return transcript, diarized, result.get("language_code")
