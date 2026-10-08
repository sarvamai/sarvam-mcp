"""Official dubbing jobs for video and audio.

POST /dubbing/jobs
PUT  {upload_url}
POST /dubbing/jobs/{job_id}/start
GET  /dubbing/jobs/{job_id}/live-status
GET  /dubbing/jobs/{job_id}/export-status

`sarvam_tools_dub` is a separate short-audio pipeline (STT → translate → TTS).
This module calls the dubbing product.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import ready_ctx
from sarvam_mcp.tools._uploads import presigned_put_headers
from sarvam_mcp.tools.vision import _guess_doc_mime

DUBBING_BASE = "/dubbing/jobs"
ExportOption = Literal["video", "audio", "mp3", "srt"]
PacePreset = Literal["slow", "moderate", "normal", "fast"]
Register = Literal[
    "formal",
    "common-indic",
    "classic-colloquial",
    "modern-colloquial",
    "academic",
    "auto",
]

_MEDIA_MIME = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_dubbing_submit",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Start an official dubbing job (POST /dubbing/jobs) for a video or audio file. "
            "Creates the job, uploads the media, and starts processing. "
            "Voice cloning is on by default. Up to 12 target languages.\n\n"
            "Poll with sarvam_tools_dubbing_status. For a short clip that should come "
            "back as a single WAV, use sarvam_tools_dub instead."
        ),
    )
    async def sarvam_dubbing_submit(
        ctx: Context,
        media_path: str = Field(description="Absolute path to the source video or audio."),
        src_lang: str = Field(description="Source BCP-47 code, e.g. en-IN."),
        target_langs: list[str] = Field(description="One or more target BCP-47 codes."),
        export_options: list[ExportOption] | None = Field(
            default=None,
            description="Formats to export: video, audio, mp3, srt.",
        ),
        voice_cloning: bool = Field(default=True),
        voice_id: str | None = Field(
            default=None,
            description="Preset voice when voice_cloning is false.",
        ),
        pace_preset: PacePreset = Field(default="normal"),
        num_speakers: int = Field(default=1, ge=1),
        register: Register = Field(default="auto"),
        job_name: str | None = Field(default=None),
        disable_watermark: bool = Field(default=False),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        path = Path(media_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Media file not found: {path}")
        if not target_langs:
            raise ValueError("target_langs must contain at least one language.")

        body: dict[str, Any] = {
            "src_lang": src_lang,
            "target_langs": target_langs,
            "voice_cloning": voice_cloning,
            "pace_preset": pace_preset,
            "num_speakers": num_speakers,
            "register": register,
            "disable_watermark": disable_watermark,
            "editor_flow": False,
            "job_name": job_name or path.name,
        }
        if export_options:
            body["export_options"] = list(export_options)
        if voice_id:
            body["voice_id"] = voice_id

        with measure_tool() as metrics:
            created, call = await sc.client.post_json(DUBBING_BASE, json_body=body)
            metrics.merge(call)
            data = created.get("data") if isinstance(created, dict) else None
            payload = data if isinstance(data, dict) else created
            job_id = payload.get("job_id")
            upload_url = payload.get("upload_url")
            if not job_id or not upload_url:
                raise RuntimeError(f"Dubbing create did not return job_id and upload_url: {created!r}")
            await ctx.info(f"Uploading {path.name} for dubbing job {job_id}…")
            await sc.client.put_external(
                upload_url,
                path.read_bytes(),
                headers=presigned_put_headers(_media_mime(path), azure=True),
            )
            started, call = await sc.client.post_json(
                f"{DUBBING_BASE}/{job_id}/start", json_body={}
            )
            metrics.merge(call)

        return {
            "job_id": job_id,
            "src_lang": src_lang,
            "target_langs": target_langs,
            "start": started,
            "next_steps": "Poll sarvam_tools_dubbing_status(job_id) until status is completed.",
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_dubbing_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll a dubbing job. live-status reports pipeline progress. "
            "export-status returns signed download URLs per language and format "
            "(video, audio, mp3, srt). URLs last about 24 hours."
        ),
    )
    async def sarvam_dubbing_status(
        ctx: Context,
        job_id: str = Field(description="Job id from sarvam_tools_dubbing_submit."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            live, call = await sc.client.get_json(f"{DUBBING_BASE}/{job_id}/live-status")
            metrics.merge(call)
            exports, call = await sc.client.get_json(
                f"{DUBBING_BASE}/{job_id}/export-status",
                params={"limit": 100},
            )
            metrics.merge(call)

        live_data = _unwrap(live)
        export_data = _unwrap(exports)
        return {
            "job_id": job_id,
            "status": live_data.get("status"),
            "progress": live_data.get("progress"),
            "current_step_label": live_data.get("current_step_label"),
            "error_message": live_data.get("error_message"),
            "exports": export_data.get("exports"),
            "observability": metrics.to_response_block(),
        }


def _unwrap(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        inner = payload.get("data")
        if isinstance(inner, dict):
            return inner
        return payload
    return {}


def _media_mime(path: Path) -> str:
    return _MEDIA_MIME.get(path.suffix.lower().lstrip("."), _guess_doc_mime(path))
