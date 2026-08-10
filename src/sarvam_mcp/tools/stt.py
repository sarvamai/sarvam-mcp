"""Speech-to-text tools — transcribe (Saaras v4), translate (legacy), batch jobs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

import httpx
from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, ready_ctx, resolve_file_input

STT_PATH = "/speech-to-text"
STT_TRANSLATE_PATH = "/speech-to-text-translate"
STT_JOB_BASE = "/speech-to-text/job/v1"
STT_JOB_UPLOAD = f"{STT_JOB_BASE}/upload-files"
STT_JOB_DOWNLOAD = f"{STT_JOB_BASE}/download-files"

MAX_POLL_ATTEMPTS = 90
POLL_INTERVAL_SECONDS = 2

SttModel = Literal["saaras:v4", "saaras:v3"]

# Models whose /speech-to-text call accepts the `mode` form field.
_MODE_CAPABLE_MODELS = {"saaras:v4", "saaras:v3"}

SttMode = Literal["transcribe", "translate", "verbatim", "translit", "codemix"]

InputAudioCodec = Literal["pcm_s16le", "pcm_l16", "pcm_raw"]

# Legacy model types kept for the deprecated translate tool.
SaarasModel = Literal["saaras:v4", "saaras:v3", "saaras:v3-realtime", "saaras:v2.5"]


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
                    if model in _MODE_CAPABLE_MODELS:
                        data["mode"] = mode
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
                "Prefer using sarvam_tools_stt_transcribe with mode='translate' and saaras:v4."
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
                "mode='translate' and model='saaras:v4'."
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
            "Supports diarization, timestamps, and all Saaras v4/v3 output modes."
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
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path, file_base64=audio_base64,
            file_url=audio_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
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

                create_resp, call = await sc.client.post_json(
                    STT_JOB_BASE, json_body={"job_parameters": job_params}
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

                if not transcript:
                    download_urls = status_resp.get("download_urls", {})
                    if download_urls:
                        await ctx.info("Downloading transcript…")
                        dl_url = next(iter(download_urls.values()))["file_url"]
                        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as dl:
                            dl_resp = await dl.get(dl_url)
                        if dl_resp.is_success:
                            dl_body = dl_resp.json()
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
