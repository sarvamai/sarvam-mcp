"""Speech-to-text tools — transcribe (Saaras v3), translate (legacy), batch jobs."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, ready_ctx

STT_PATH = "/speech-to-text"
STT_TRANSLATE_PATH = "/speech-to-text-translate"
STT_BATCH_PATH = "/speech-to-text/job/init"
STT_BATCH_STATUS_PATH = "/speech-to-text/job/status"

SttModel = Literal["saaras:v3"]

SttMode = Literal["transcribe", "translate", "verbatim", "translit", "codemix"]

InputAudioCodec = Literal["pcm_s16le", "pcm_l16", "pcm_raw"]

# Legacy model types kept for the deprecated translate tool.
SaarasModel = Literal["saaras:v3", "saaras:v3-realtime", "saaras:v2.5"]


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
        audio_path: str = Field(
            description=(
                "Absolute path to the audio file. Supports wav, mp3, ogg, "
                "flac, m4a, webm, aac, opus, amr, wma."
            ),
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
        path = Path(audio_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")

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
        audio_path: str = Field(description="Absolute path to the audio file."),
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
        path = Path(audio_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")

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
            "Initialize a batch (long-audio) transcription job. Returns a "
            "`job_id` plus pre-signed Azure Blob URLs: upload your audio "
            "file(s) to `input_storage_path`, then call "
            "`sarvam_stt_batch_status` to poll completion. Outputs land at "
            "`output_storage_path`. Use this for files >30s."
        ),
    )
    async def sarvam_stt_batch_submit(
        ctx: Context,
        language_code: LanguageCode = Field(default="unknown"),
        model: SttModel = Field(default="saaras:v3"),
        with_timestamps: bool = Field(default=False),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        body: dict[str, Any] = {"model": model, "with_timestamps": with_timestamps}
        if language_code != "unknown":
            body["language_code"] = language_code

        with measure_tool() as metrics:
            payload, call = await sc.client.post_json(STT_BATCH_PATH, json_body=body)
            metrics.merge(call)

        return {
            "job_id": payload.get("job_id"),
            "input_storage_path": payload.get("input_storage_path"),
            "output_storage_path": payload.get("output_storage_path"),
            "storage_container_type": payload.get("storage_container_type"),
            "submitted_at": time.time(),
            "next_steps": (
                "1) Upload your audio file(s) to `input_storage_path` (Azure SAS-signed). "
                "2) Poll with sarvam_stt_batch_status(job_id). "
                "3) Read results from `output_storage_path` once status='completed'."
            ),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_stt_batch_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll the status of a batch transcription job. Returns the transcript "
            "once `status == 'completed'`."
        ),
    )
    async def sarvam_stt_batch_status(
        ctx: Context,
        job_id: str = Field(description="The job_id returned by sarvam_stt_batch_submit."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.get_json(
                STT_BATCH_STATUS_PATH, params={"job_id": job_id}
            )
            metrics.merge(call)

        return {
            "job_id": job_id,
            "status": payload.get("job_state") or payload.get("status"),
            "transcript": payload.get("transcript"),
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
