"""Speech-to-text tools — transcribe (Saaras v3), translate (legacy), batch jobs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

import httpx
from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.http.errors import SarvamBadRequestError
from sarvam_mcp.observability import ToolMetrics, measure_tool
from sarvam_mcp.tools._common import LanguageCode, ready_ctx, resolve_file_input

STT_PATH = "/speech-to-text"
STT_TRANSLATE_PATH = "/speech-to-text-translate"
STT_JOB_BASE = "/speech-to-text/job/v1"
STT_JOB_UPLOAD = f"{STT_JOB_BASE}/upload-files"
STT_JOB_DOWNLOAD = f"{STT_JOB_BASE}/download-files"

MAX_POLL_ATTEMPTS = 90
POLL_INTERVAL_SECONDS = 2

# /download-files can reject a job as not-yet-Completed for a few seconds
# right after /status already reports it terminal — a backend consistency
# lag between the two endpoints, observed most on fast-completing jobs.
DOWNLOAD_READY_ATTEMPTS = 3
DOWNLOAD_READY_RETRY_DELAY_SECONDS = 3

SttModel = Literal["saaras:v3"]

SttMode = Literal["transcribe", "translate", "verbatim", "translit", "codemix"]

InputAudioCodec = Literal["pcm_s16le", "pcm_l16", "pcm_raw"]

# Legacy model types kept for the deprecated translate tool.
SaarasModel = Literal["saaras:v3", "saaras:v3-realtime", "saaras:v2.5"]


async def stt_batch_transcribe(
    sc: ServerContext,
    ctx: Context,
    audio_path: Path,
    *,
    language_code: str = "unknown",
    mode: str = "transcribe",
    with_timestamps: bool = False,
    with_diarization: bool = False,
    num_speakers: int | None = None,
    model: str = "saaras:v3",
    metrics: ToolMetrics | None = None,
) -> dict[str, Any]:
    """Run the full batch STT flow: create job → upload → start → poll → extract.

    Chains the five manual steps (create, register upload, PUT to blob, start,
    poll-until-terminal) that ``sarvam_tools_stt_batch_submit`` exposes as one
    tool call. Shared here so other composite workflows (e.g. ``sv_meet``) can
    reuse batch/diarized transcription without re-implementing the polling loop.

    Returns a dict shaped like the tool response, minus ``observability`` —
    callers merge that in from their own ``metrics`` after their
    ``measure_tool()`` block exits. On a poll timeout the dict has only
    ``job_id`` / ``job_state`` / ``error`` — no transcript fields.
    """
    if metrics is None:
        metrics = ToolMetrics(latency_ms=0.0)

    # Step 1: Create the job
    await ctx.info("Creating batch STT job…")
    job_params: dict[str, Any] = {
        "language_code": language_code if language_code != "unknown" else None,
        "model": model,
        "mode": mode,
        "with_timestamps": with_timestamps,
        "with_diarization": with_diarization,
    }
    if num_speakers is not None:
        job_params["num_speakers"] = num_speakers
    job_params = {k: v for k, v in job_params.items() if v is not None}

    create_resp, call = await sc.client.post_json(STT_JOB_BASE, json_body={"job_parameters": job_params})
    metrics.merge(call)
    job_id = create_resp["job_id"]

    # Step 2: Register files → get upload SAS URLs
    await ctx.info(f"Registering audio file for job {job_id}…")
    upload_resp, call = await sc.client.post_json(
        STT_JOB_UPLOAD,
        json_body={"job_id": job_id, "files": [audio_path.name]},
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
    with audio_path.open("rb") as fh:
        blob_metrics = await sc.client.put_blob(
            presigned_url,
            fh.read(),
            content_type=_guess_audio_mime(audio_path),
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
        status_resp, call = await sc.client.get_json(f"{STT_JOB_BASE}/{job_id}/status")
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
        }

    # Step 6: Extract transcript
    result = status_resp.get("result") or {}
    transcript = result.get("transcript") or status_resp.get("transcript")

    if not transcript:
        # The status response never inlines the result for a job whose output
        # wasn't returned directly — the documented flow is to fetch the SAS
        # URL for each output file via /download-files, then GET it.
        file_names = [
            output["file_name"]
            for detail in status_resp.get("job_details") or []
            for output in detail.get("outputs") or []
            if output.get("file_name")
        ]
        if file_names:
            await ctx.info("Fetching output file list…")
            download_urls = await _fetch_download_urls(sc, job_id, file_names, metrics)

            await ctx.info("Downloading transcript…")
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as dl:
                for file_details in download_urls.values():
                    dl_url = file_details.get("file_url")
                    if not dl_url:
                        continue
                    dl_resp = await dl.get(dl_url)
                    if not dl_resp.is_success:
                        continue
                    dl_body = dl_resp.json()
                    if dl_body.get("transcript"):
                        transcript = dl_body["transcript"]
                        result = dl_body
                        break

    return {
        "job_id": job_id,
        "job_state": status_resp.get("job_state"),
        "transcript": transcript or "",
        "language_code": result.get("language_code"),
        "diarized_transcript": result.get("diarized_transcript"),
        "timestamps": result.get("timestamps"),
    }


async def _fetch_download_urls(
    sc: ServerContext,
    job_id: str,
    file_names: list[str],
    metrics: ToolMetrics,
) -> dict[str, Any]:
    """POST /download-files, retrying briefly on a transient consistency lag.

    Observed live: /download-files can reject a job as not-yet-Completed for
    a few seconds right after /status already reports it terminal, most often
    on fast-completing jobs. Retries only on that specific rejection — any
    other SarvamBadRequestError (a real caller-side problem) is not retried.
    """
    for attempt in range(DOWNLOAD_READY_ATTEMPTS):
        try:
            dl_list_resp, call = await sc.client.post_json(
                STT_JOB_DOWNLOAD,
                json_body={"job_id": job_id, "files": file_names},
            )
        except SarvamBadRequestError as exc:
            if "COMPLETED state" not in str(exc) or attempt == DOWNLOAD_READY_ATTEMPTS - 1:
                raise RuntimeError(
                    f"Job {job_id} polled as terminal, but /download-files still "
                    f"rejects it after {attempt + 1} attempt(s): {exc}"
                ) from exc
            await asyncio.sleep(DOWNLOAD_READY_RETRY_DELAY_SECONDS * (attempt + 1))
            continue
        metrics.merge(call)
        return dl_list_resp.get("download_urls") or {}

    raise AssertionError("unreachable")  # loop always returns or raises


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_stt_transcribe",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Transcribe an audio file in any of 23 Indian languages using Saaras v3.\n\n"
            "Saaras v3 supports multiple output modes via the `mode` parameter:\n"
            "  • `transcribe` (default) — standard transcription in the original language\n"
            "  • `translate` — speech from any Indic language directly to English text\n"
            "  • `verbatim` — exact word-for-word, no normalization, filler words preserved\n"
            "  • `translit` — romanization to Latin/Roman script\n"
            "  • `codemix` — English words in English, Indic words in native script\n\n"
            "The default `language_code='unknown'` auto-detects, but specifying the "
            "language (e.g. `hi-IN`, `ta-IN`) gives better accuracy.\n"
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
                "Output mode (Saaras v3 only). "
                "'transcribe' (default) | 'translate' (→ English) | "
                "'verbatim' | 'translit' (→ Roman) | 'codemix'."
            ),
        ),
        with_timestamps: bool = Field(
            default=False, description="Include word-level timestamps in the response."
        ),
        model: SttModel = Field(
            default="saaras:v3",
            description="Saaras v3 (recommended STT model for Indic audio).",
        ),
        input_audio_codec: InputAudioCodec | None = Field(
            default=None,
            description=(
                "Required only for PCM files. One of 'pcm_s16le', 'pcm_l16', 'pcm_raw'. "
                "PCM files are supported only at 16kHz sample rate."
            ),
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    files = {"file": (path.name, fh, _guess_audio_mime(path))}
                    data: dict[str, Any] = {
                        "model": model,
                        "language_code": language_code,
                        "with_timestamps": str(with_timestamps).lower(),
                    }
                    if model == "saaras:v3" and mode != "transcribe":
                        data["mode"] = mode
                    elif model == "saaras:v3":
                        data["mode"] = "transcribe"
                    if input_audio_codec is not None:
                        data["input_audio_codec"] = input_audio_codec
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
        name="sarvam_tools_stt_translate",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "DEPRECATED: Use `sarvam_tools_stt_transcribe` with `mode='translate'` instead.\n\n"
            "Transcribe an Indic-language audio file directly into English text "
            "using the legacy `/speech-to-text-translate` endpoint. "
            "This endpoint will be removed in a future version."
        ),
    )
    async def sarvam_stt_translate(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to the audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio data."),
        audio_url: str | None = Field(default=None, description="URL to fetch the audio file from."),
        filename: str | None = Field(default=None, description="Filename with extension (for base64/URL)."),
        with_diarization: bool = Field(
            default=False, description="Return per-speaker turns."
        ),
        model: SaarasModel = Field(
            default="saaras:v2.5",
            description=(
                "Legacy Saaras model for the /speech-to-text-translate endpoint. "
                "Prefer using sarvam_tools_stt_transcribe with mode='translate' and saaras:v3."
            ),
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    files = {"file": (path.name, fh, _guess_audio_mime(path))}
                    data: dict[str, Any] = {
                        "model": model,
                        "with_diarization": str(with_diarization).lower(),
                    }
                    payload, call = await sc.client.post_multipart(
                        STT_TRANSLATE_PATH, data=data, files=files
                    )
                metrics.merge(call)

        return {
            "transcript": payload.get("transcript", ""),
            "language_code": payload.get("language_code"),
            "diarized_transcript": payload.get("diarized_transcript"),
            "deprecation_notice": (
                "This tool uses the legacy /speech-to-text-translate endpoint. "
                "Migrate to sarvam_tools_stt_transcribe with "
                "mode='translate' and model='saaras:v3'."
            ),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_stt_batch_submit",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Transcribe a long audio file (>30 s) using the batch job pipeline. "
            "Runs the full flow automatically: create job → upload audio to Azure "
            "Blob → start processing → poll until complete → return transcript.\n\n"
            "Supports diarization, timestamps, and all Saaras v3 output modes."
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
        model: SttModel = Field(default="saaras:v3"),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                result = await stt_batch_transcribe(
                    sc,
                    ctx,
                    path,
                    language_code=language_code,
                    mode=mode,
                    with_timestamps=with_timestamps,
                    with_diarization=with_diarization,
                    num_speakers=num_speakers,
                    model=model,
                    metrics=metrics,
                )

        return {**result, "observability": metrics.to_response_block()}

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
        return {
            "job_id": job_id,
            "job_state": payload.get("job_state"),
            "transcript": result.get("transcript") or payload.get("transcript"),
            "download_urls": payload.get("download_urls"),
            "raw": payload,
            "observability": metrics.to_response_block(),
        }


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
