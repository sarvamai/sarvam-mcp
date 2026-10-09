"""Speech-to-text — REST, batch v1, and realtime WebSocket."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import wave
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, ready_ctx, resolve_file_input

STT_PATH = "/speech-to-text"
STT_JOB_BASE = "/speech-to-text/job/v1"
STT_REALTIME_PATH = "/speech-to-text-realtime/ws"
STT_JOB_UPLOAD = f"{STT_JOB_BASE}/upload-files"
STT_JOB_DOWNLOAD = f"{STT_JOB_BASE}/download-files"

MAX_POLL_ATTEMPTS = 90
POLL_INTERVAL_SECONDS = 2

SttModel = Literal["saaras:v4", "saaras:v3"]

# Models whose /speech-to-text call accepts the `mode` form field.
_MODE_CAPABLE_MODELS = {"saaras:v4", "saaras:v3"}

SttMode = Literal["transcribe", "translate", "verbatim", "translit", "codemix"]
RealtimeModel = Literal["saaras:v3-realtime", "saaras:v4"]
StreamType = Literal["fast", "balanced", "simulated"]

InputAudioCodec = Literal["pcm_s16le", "pcm_l16", "pcm_raw"]


def _stt_language_code(language_code: LanguageCode) -> LanguageCode:
    """Map the shared auto-detect token to the value the STT API expects.

    The shared ``LanguageCode`` enum carries two auto-detect tokens: ``"auto"``
    (Translate/Transliterate) and ``"unknown"`` (STT). The STT endpoints only
    accept ``"unknown"``, so normalize ``"auto"`` to it, mirroring how
    ``translate``/``transliterate`` normalize ``"unknown"`` to ``"auto"``.
    """
    return "unknown" if language_code == "auto" else language_code


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_stt_transcribe",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Transcribe an audio file in any of 23 Indian languages using Saaras v4.\n\n"
            "Saaras v4 (like v3) supports multiple output modes via the `mode` parameter:\n"
            "  • `transcribe` (default) — standard transcription in the original language\n"
            "  • `translate` — speech from any Indic language directly to English text\n"
            "  • `verbatim` — exact word-for-word, no normalization, filler words preserved\n"
            "  • `translit` — romanization to Latin/Roman script\n"
            "  • `codemix` — English words in English, Indic words in native script\n\n"
            "The default `language_code='unknown'` auto-detects, but specifying the "
            "language (e.g. `hi-IN`, `ta-IN`) gives better accuracy.\n"
            "Speech-to-English uses this tool with `mode='translate'`.\n"
            "For very long files (>30s), prefer `sarvam_stt_batch_submit`."
        ),
    )
    async def sarvam_stt_transcribe(
        ctx: Context,
        audio_path: str | None = Field(
            default=None,
            description="Local path to the audio file.",
        ),
        audio_base64: str | None = Field(
            default=None,
            description="Base64-encoded audio data (for remote MCP).",
        ),
        audio_url: str | None = Field(
            default=None,
            description="URL to fetch the audio file from.",
        ),
        filename: str | None = Field(
            default=None,
            description="Filename with extension, e.g. 'recording.wav'. Required for base64/URL inputs.",
        ),
        language_code: LanguageCode = Field(
            default="unknown",
            description="BCP-47 code, e.g. 'hi-IN'. Use 'unknown' to auto-detect.",
        ),
        mode: SttMode = Field(
            default="transcribe",
            description=(
                "Output mode (Saaras v3/v4 only). "
                "'transcribe' (default) | 'translate' (→ English) | "
                "'verbatim' | 'translit' (→ Roman) | 'codemix'."
            ),
        ),
        with_timestamps: bool = Field(
            default=False, description="Include word-level timestamps in the response."
        ),
        model: SttModel = Field(
            default="saaras:v4",
            description="Saaras v4 (recommended, latest STT model for Indic audio). Falls back to saaras:v3 if needed.",
        ),
        input_audio_codec: InputAudioCodec | None = Field(
            default=None,
            description=(
                "Required only for PCM files. One of 'pcm_s16le', 'pcm_l16', 'pcm_raw'. "
                "PCM files are supported only at 16kHz sample rate."
            ),
        ),
        keyterms: list[str] | None = Field(
            default=None,
            description=(
                "saaras:v4 only. Up to 50 domain-specific terms (max 64 chars each) "
                "to bias recognition toward — names, jargon, brand terms. Ignored "
                "by saaras:v3."
            ),
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        _check_keyterms(keyterms, model)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    files = {"file": (path.name, fh, _guess_audio_mime(path))}
                    data: dict[str, Any] = {
                        "model": model,
                        "language_code": _stt_language_code(language_code),
                        "with_timestamps": str(with_timestamps).lower(),
                    }
                    if model in _MODE_CAPABLE_MODELS:
                        data["mode"] = mode
                    if input_audio_codec is not None:
                        data["input_audio_codec"] = input_audio_codec
                    if keyterms and model == "saaras:v4":
                        data["keyterms"] = json.dumps(keyterms)
                    payload, call = await sc.client.post_multipart(
                        STT_PATH, data=data, files=files
                    )
                metrics.merge(call)

        return {
            "transcript": payload.get("transcript", ""),
            "language_code": payload.get("language_code"),
            "language_probability": payload.get("language_probability"),
            "diarized_transcript": payload.get("diarized_transcript"),
            "timestamps": payload.get("timestamps"),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_stt_batch_submit",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Transcribe a long audio file (>30 s) using the batch job pipeline. "
            "Runs the full flow automatically: create job → upload audio to Azure "
            "Blob → start processing → poll until complete → return transcript.\n\n"
            "Supports diarization, timestamps, all Saaras v4/v3 output modes, "
            "v4-only keyterms, and an optional webhook callback instead of polling."
        ),
    )
    async def sarvam_stt_batch_submit(
        ctx: Context,
        audio_path: str | None = Field(
            default=None, description="Local path to the audio file.",
        ),
        audio_base64: str | None = Field(
            default=None, description="Base64-encoded audio data (for remote MCP).",
        ),
        audio_url: str | None = Field(
            default=None, description="URL to fetch the audio file from.",
        ),
        filename: str | None = Field(
            default=None, description="Filename with extension (for base64/URL).",
        ),
        language_code: LanguageCode = Field(
            default="unknown",
            description="BCP-47 code, e.g. 'hi-IN'. Use 'unknown' to auto-detect.",
        ),
        mode: SttMode = Field(
            default="transcribe",
            description=(
                "Output mode. 'transcribe' (default) | 'translate' (→ English) | "
                "'verbatim' | 'translit' (→ Roman) | 'codemix'."
            ),
        ),
        with_timestamps: bool = Field(
            default=False, description="Include word-level timestamps."
        ),
        with_diarization: bool = Field(
            default=False, description="Return per-speaker turns."
        ),
        num_speakers: int | None = Field(
            default=None,
            description="Hint for diarization: expected number of speakers.",
        ),
        model: SttModel = Field(default="saaras:v4"),
        input_audio_codec: InputAudioCodec | None = Field(
            default=None,
            description=(
                "Required only for PCM files. One of 'pcm_s16le', 'pcm_l16', 'pcm_raw'. "
                "PCM files are supported only at 16kHz sample rate."
            ),
        ),
        keyterms: list[str] | None = Field(
            default=None,
            description=(
                "saaras:v4 only. Up to 50 domain-specific terms (max 64 chars each) "
                "to bias recognition toward. Ignored by saaras:v3."
            ),
        ),
        callback_url: str | None = Field(
            default=None,
            description=(
                "Optional webhook URL to notify on job completion, instead of "
                "polling. Requires callback_auth_token too."
            ),
        ),
        callback_auth_token: str | None = Field(
            default=None,
            description="Bearer token Sarvam will send with the callback_url webhook call.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        _check_keyterms(keyterms, model)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                # Step 1: Create the job
                await ctx.info("Creating batch STT job…")
                job_params: dict[str, Any] = {
                    "language_code": (
                        None if _stt_language_code(language_code) == "unknown" else language_code
                    ),
                    "model": model,
                    "mode": mode,
                    "with_timestamps": with_timestamps,
                    "with_diarization": with_diarization,
                    "input_audio_codec": input_audio_codec,
                }
                if num_speakers is not None:
                    job_params["num_speakers"] = num_speakers
                if keyterms and model == "saaras:v4":
                    job_params["keyterms"] = keyterms
                job_params = {k: v for k, v in job_params.items() if v is not None}

                create_body: dict[str, Any] = {"job_parameters": job_params}
                if callback_url is not None:
                    create_body["callback"] = {
                        "url": callback_url,
                        "auth_token": callback_auth_token,
                    }

                create_resp, call = await sc.client.post_json(
                    STT_JOB_BASE, json_body=create_body
                )
                metrics.merge(call)
                job_id = create_resp["job_id"]

                # Step 2: Register files → get upload SAS URLs
                await ctx.info(f"Registering audio file for job {job_id}…")
                upload_resp, call = await sc.client.post_json(
                    STT_JOB_UPLOAD,
                    json_body={"job_id": job_id, "files": [path.name]},
                )
                metrics.merge(call)

                upload_urls = upload_resp.get("upload_urls", {})
                if not upload_urls:
                    raise RuntimeError(f"No upload URLs returned for job {job_id}")

                # Step 3: PUT audio bytes to Azure Blob
                await ctx.info("Uploading audio to Azure Blob…")
                file_details = next(iter(upload_urls.values()))
                presigned_url = file_details["file_url"]
                file_metadata = file_details.get("file_metadata") or {}

                extra_headers = {str(k): str(v) for k, v in file_metadata.items()}
                with path.open("rb") as fh:
                    blob_metrics = await sc.client.put_blob(
                        presigned_url,
                        fh.read(),
                        content_type=_guess_audio_mime(path),
                        extra_headers=extra_headers,
                    )
                metrics.merge(blob_metrics)

                # Step 4: Start the job
                await ctx.info("Starting batch processing…")
                start_resp, call = await sc.client.post_json(
                    f"{STT_JOB_BASE}/{job_id}/start",
                    json_body={"job_id": job_id, "job_parameters": job_params},
                )
                metrics.merge(call)

                # Step 5: Poll for completion
                await ctx.info("Polling for completion…")
                terminal_states = {"Completed", "PartiallyCompleted", "Failed", "failed", "error"}
                status_resp: dict[str, Any] = {}
                for attempt in range(MAX_POLL_ATTEMPTS):
                    status_resp, call = await sc.client.get_json(
                        f"{STT_JOB_BASE}/{job_id}/status"
                    )
                    metrics.merge(call)
                    job_state = status_resp.get("job_state", "")
                    if job_state in terminal_states:
                        break
                    if (attempt + 1) % 5 == 0:
                        await ctx.report_progress(attempt + 1, MAX_POLL_ATTEMPTS)
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                else:
                    return {
                        "job_id": job_id,
                        "job_state": status_resp.get("job_state", "timeout"),
                        "error": (
                            f"Job did not complete within "
                            f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s. "
                            f"Poll manually with sarvam_tools_stt_batch_status."
                        ),
                        "observability": metrics.to_response_block(),
                    }

                # Step 6: Extract transcript
                result = status_resp.get("result") or {}
                transcript = result.get("transcript") or status_resp.get("transcript")

                if not transcript and status_resp.get("job_state") in (
                    "Completed",
                    "PartiallyCompleted",
                ):
                    await ctx.info("Downloading transcript…")
                    dl_body, call = await _fetch_first_output(sc, job_id, status_resp)
                    if call is not None:
                        metrics.merge(call)
                    if dl_body:
                        transcript = dl_body.get("transcript", "")
                        result = dl_body

        return {
            "job_id": job_id,
            "job_state": status_resp.get("job_state"),
            "transcript": transcript or "",
            "language_code": result.get("language_code"),
            "diarized_transcript": result.get("diarized_transcript"),
            "timestamps": result.get("timestamps"),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_stt_batch_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll the status of a batch transcription job. Returns the transcript "
            "once `job_state == 'Completed'`."
        ),
    )
    async def sarvam_stt_batch_status(
        ctx: Context,
        job_id: str = Field(description="The job_id returned by sarvam_stt_batch_submit."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.get_json(
                f"{STT_JOB_BASE}/{job_id}/status"
            )
            metrics.merge(call)

            result = payload.get("result") or {}
            transcript = result.get("transcript") or payload.get("transcript")
            if not transcript and payload.get("job_state") in (
                "Completed",
                "PartiallyCompleted",
            ):
                dl_body, dl_call = await _fetch_first_output(sc, job_id, payload)
                if dl_call is not None:
                    metrics.merge(dl_call)
                transcript = (dl_body or {}).get("transcript")

        return {
            "job_id": job_id,
            "job_state": payload.get("job_state"),
            "transcript": transcript,
            "output_files": _output_filenames(payload),
            "raw": payload,
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_stt_batch_download",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Get fresh presigned download URLs for specific output files of a "
            "completed batch STT job. Use this if the URLs from "
            "sarvam_tools_stt_batch_status have expired. Requires the exact output "
            "filenames (e.g. '0.json') — get these from a prior "
            "sarvam_tools_stt_batch_status call's `output_files`."
        ),
    )
    async def sarvam_stt_batch_download(
        ctx: Context,
        job_id: str = Field(description="The job_id returned by sarvam_tools_stt_batch_submit."),
        files: list[str] = Field(
            description=(
                "Exact output filenames to fetch fresh URLs for, e.g. ['0.json']. "
                "Get these from sarvam_tools_stt_batch_status's `output_files`."
            ),
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.post_json(
                STT_JOB_DOWNLOAD, json_body={"job_id": job_id, "files": files}
            )
            metrics.merge(call)

        return {
            "job_id": job_id,
            "job_state": payload.get("job_state"),
            "download_urls": payload.get("download_urls", payload),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_stt_realtime",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Transcribe a mono 16-bit WAV (8000 or 16000 Hz) over "
            "GET /speech-to-text-realtime/ws. Use this when you need the realtime "
            "protocol (partials, VAD). Compressed audio and long recordings belong "
            "on sarvam_tools_stt_transcribe or sarvam_tools_stt_batch_submit.\n\n"
            "Default model is saaras:v3-realtime. saaras:v4 adds keyterms. "
            "`language_code='unknown'` is sent as `auto`."
        ),
    )
    async def sarvam_stt_realtime(
        ctx: Context,
        audio_path: str = Field(
            description="Absolute path to a mono 16-bit PCM WAV at 8 kHz or 16 kHz.",
        ),
        language_code: LanguageCode = Field(default="unknown"),
        model: RealtimeModel = Field(default="saaras:v3-realtime"),
        mode: SttMode = Field(default="transcribe"),
        stream_type: StreamType = Field(
            default="simulated",
            description="'simulated' returns finals only. 'fast' or 'balanced' also emit partials.",
        ),
        keyterms: list[str] | None = Field(
            default=None, description="Saaras v4 only. Up to 50 terms."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        _check_keyterms(keyterms, model)
        path = Path(audio_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")
        pcm, sample_rate = _read_realtime_wav(path)

        params: dict[str, str] = {
            "language_code": "auto" if language_code == "unknown" else language_code,
            "model": model,
            "mode": mode,
            "encoding": "linear16",
            "sample_rate": str(sample_rate),
            "stream_type": stream_type,
        }
        if keyterms and model == "saaras:v4":
            params["keyterms"] = json.dumps(keyterms)
        ws_url = _ws_url(sc.config.base_url, STT_REALTIME_PATH, params)

        finals: list[dict[str, Any]] = []
        partials: list[str] = []
        with measure_tool() as metrics:
            async with sc.client.stream_ws(ws_url) as ws:
                sender = asyncio.create_task(_send_realtime_audio(ws, pcm, sample_rate))
                try:
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=120)
                        event = _parse_ws(raw)
                        kind = event.get("event") or event.get("type")
                        if kind == "transcript.partial" and event.get("text"):
                            partials.append(event["text"])
                        elif kind == "transcript.final":
                            finals.append(event)
                        elif kind == "session.end":
                            break
                        elif kind == "error":
                            data = event.get("data") or {}
                            fatal = event.get("is_fatal") or (
                                data.get("is_fatal") if isinstance(data, dict) else False
                            )
                            message = event.get("message") or data or event
                            if fatal:
                                raise RuntimeError(f"Realtime STT error: {message}")
                finally:
                    sender.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await sender

        transcript = " ".join(
            str(item.get("text") or "") for item in finals if item.get("text")
        ).strip()
        return {
            "transcript": transcript,
            "finals": finals,
            "partials": partials[-5:],
            "model": model,
            "observability": metrics.to_response_block(),
        }


def _check_keyterms(keyterms: list[str] | None, model: str) -> None:
    if not keyterms:
        return
    if model != "saaras:v4":
        raise ValueError("keyterms are supported only on saaras:v4.")
    if len(keyterms) > 50:
        raise ValueError("keyterms accepts at most 50 terms.")
    too_long = [term for term in keyterms if len(term) > 64]
    if too_long:
        raise ValueError(f"keyterms must be 64 characters or fewer: {too_long[:3]}")


def _output_filenames(status: dict[str, Any]) -> list[str]:
    """Output file names listed under ``job_details[].outputs[]`` of a status payload."""
    return [
        o["file_name"]
        for detail in status.get("job_details") or []
        for o in detail.get("outputs") or []
        if o.get("file_name")
    ]


async def _fetch_first_output(
    sc: Any, job_id: str, status: dict[str, Any]
) -> tuple[dict[str, Any] | None, Any | None]:
    """Resolve a fresh presigned URL for the job's first output file and load its JSON."""
    files = _output_filenames(status)[:1]
    if not files:
        return None, None
    resp, call = await sc.client.post_json(
        STT_JOB_DOWNLOAD, json_body={"job_id": job_id, "files": files}
    )
    url = (resp.get("download_urls") or {}).get(files[0], {}).get("file_url")
    if not url:
        return None, call
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as dl:
        dl_resp = await dl.get(url)
    return (dl_resp.json() if dl_resp.is_success else None), call


def _read_realtime_wav(path: Path) -> tuple[bytes, int]:
    try:
        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            width = wf.getsampwidth()
            rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
    except wave.Error as exc:
        raise ValueError(
            "Realtime STT needs a PCM WAV. Use sarvam_tools_stt_transcribe "
            "for mp3 and other compressed formats."
        ) from exc
    if channels != 1 or width != 2 or rate not in (8000, 16000):
        raise ValueError(
            "Realtime STT accepts mono 16-bit WAV at 8000 or 16000 Hz "
            f"(got channels={channels}, sampwidth={width}, rate={rate})."
        )
    return frames, rate


async def _send_realtime_audio(ws: Any, pcm: bytes, sample_rate: int) -> None:
    # ~100 ms of 16-bit mono audio.
    chunk_size = sample_rate // 10 * 2
    for start in range(0, len(pcm), chunk_size):
        chunk = pcm[start : start + chunk_size]
        await ws.send(
            json.dumps(
                {
                    "event": "audio_input",
                    "audio": base64.b64encode(chunk).decode("ascii"),
                }
            )
        )
        await asyncio.sleep(0)
    await ws.send(json.dumps({"event": "flush"}))
    await ws.send(json.dumps({"event": "end"}))


def _parse_ws(raw: Any) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ws_url(base_url: str, path: str, params: dict[str, str]) -> str:
    root = base_url.rstrip("/")
    if root.startswith("https://"):
        root = "wss://" + root[len("https://") :]
    elif root.startswith("http://"):
        root = "ws://" + root[len("http://") :]
    query = urlencode(params)
    return f"{root}{path}?{query}" if query else f"{root}{path}"


def _guess_audio_mime(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
        "aac": "audio/aac",
        "opus": "audio/opus",
        "amr": "audio/amr",
        "wma": "audio/x-ms-wma",
    }.get(suffix, "application/octet-stream")
