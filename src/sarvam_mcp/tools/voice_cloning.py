"""Instant Voice Cloning (Beta).

POST   /voices/create             save a reference voice -> voice_id (svc-<uuid>)
POST   /voices/clone              speak text in a saved or ad-hoc reference voice
GET    /voices                    list saved voices
GET    /voices/{voice_id}         one voice
DELETE /voices/delete/{voice_id}  remove a voice (frees a slot; Starter cap is 50 per org)
POST   /voices/watermark/detect   check audio for Sarvam's watermark (free, 5 req/min)

Voice clones are billed per 1,000 characters synthesised. Only clone voices you
have the right to use.
"""

from __future__ import annotations

import base64
import uuid
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import ready_ctx, resolve_file_input
from sarvam_mcp.tools.stt import _guess_audio_mime

VOICES_BASE = "/voices"
CREATE_MAX_BYTES = 50 * 1024 * 1024  # /voices/create: 50 MB
CLONE_REF_MAX_BYTES = 10 * 1024 * 1024  # /voices/clone ref_audio: 10 MB
WATERMARK_MAX_BYTES = 10 * 1024 * 1024  # /voices/watermark/detect: 10 MB

CloneLanguage = Literal[
    "as-IN",
    "bn-IN",
    "en-IN",
    "gu-IN",
    "hi-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
]
CloneCodec = Literal["wav", "mp3", "flac", "opus", "aac", "linear16", "mulaw", "alaw"]
CloneRate = Literal[8000, 16000, 22050, 24000, 32000, 44100, 48000]

_CODEC_EXT = {
    "wav": ("wav", "audio/wav"),
    "mp3": ("mp3", "audio/mpeg"),
    "flac": ("flac", "audio/flac"),
    "opus": ("opus", "audio/opus"),
    "aac": ("aac", "audio/aac"),
    "linear16": ("pcm", "audio/L16"),
    "mulaw": ("ulaw", "audio/basic"),
    "alaw": ("alaw", "audio/x-alaw-basic"),
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_cloned_voice_create",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Save a cloned voice from a reference recording (POST /voices/create, beta). Use 10-15 s "
            "of a single clear speaker (WAV recommended, max 50 MB). Returns a `voice_id` "
            "(svc-…) for sarvam_tools_cloned_voice_speak. The reference transcript is produced "
            "automatically; background noise is removed by default. Fails with 422 if the audio "
            "is too noisy/short/multi-speaker, and 403 TIER_LIMIT_REACHED at the per-org voice cap "
            "(50 on Starter) — delete unused voices with sarvam_tools_cloned_voice_delete."
        ),
    )
    async def sarvam_voice_create(
        ctx: Context,
        name: str = Field(min_length=1, max_length=100, description="Display name for the voice."),
        language: str = Field(description="BCP-47 code of the reference audio, e.g. 'hi-IN'."),
        audio_path: str | None = Field(
            default=None, description="Local path to the reference audio."
        ),
        audio_base64: str | None = Field(default=None, description="Base64 reference audio."),
        audio_url: str | None = Field(
            default=None, description="URL to fetch the reference audio from."
        ),
        filename: str | None = Field(
            default=None, description="Filename with extension for base64/URL input."
        ),
        style: str | None = Field(
            default=None, description="Optional style label, e.g. 'conversational'."
        ),
        gender: str | None = Field(default=None, description="Optional gender label."),
        remove_background_noise: bool = Field(
            default=True, description="Denoise the reference (default true on /voices/create)."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        data: dict[str, Any] = {
            "name": name,
            "language": language,
            "remove_background_noise": str(remove_background_noise).lower(),
        }
        if style:
            data["style"] = style
        if gender:
            data["gender"] = gender
        async with resolve_file_input(
            file_path=audio_path,
            file_base64=audio_base64,
            file_url=audio_url,
            filename=filename,
            max_bytes=CREATE_MAX_BYTES,
        ) as path:
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    payload, call = await sc.client.post_multipart(
                        f"{VOICES_BASE}/create",
                        data=data,
                        files={"file": (path.name, fh, _guess_audio_mime(path))},
                    )
                metrics.merge(call)
        body = payload if isinstance(payload, dict) else {}
        info = body.get("data") if isinstance(body.get("data"), dict) else {}
        return {
            "voice_id": info.get("voice_id"),
            "status": info.get("status"),
            "reference_text": info.get("reference_text"),
            "background_noise_removed": info.get("background_noise_removed"),
            "raw": body,
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_cloned_voice_speak",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Speak text in a cloned voice (POST /voices/clone, beta). Give EXACTLY ONE of `voice_id` "
            "(from sarvam_tools_cloned_voice_create) or an ad-hoc reference clip (`ref_audio_path`/"
            "`ref_audio_base64`, ≤10 MB, ≤15 s). `text` ≤1000 chars. `language_code` is optional "
            "(auto-detected from the text). `pace` and `max_audio_duration` are mutually exclusive. "
            "Audio is written under SARVAM_MCP_BASE_PATH."
        ),
    )
    async def sarvam_voice_speak(
        ctx: Context,
        text: str = Field(
            min_length=1, max_length=1000, description="Text to speak (max 1000 chars)."
        ),
        voice_id: str | None = Field(default=None, description="Saved voice id (svc-…)."),
        ref_audio_path: str | None = Field(
            default=None, description="Local reference clip (ad-hoc clone)."
        ),
        ref_audio_base64: str | None = Field(default=None, description="Base64 reference clip."),
        filename: str | None = Field(
            default=None, description="Filename with extension for base64 reference."
        ),
        language_code: CloneLanguage | None = Field(
            default=None, description="Omit to auto-detect from text."
        ),
        pace: float | None = Field(
            default=None, ge=0.5, le=2.0, description="0.5-2.0. Exclusive with max_audio_duration."
        ),
        output_audio_codec: CloneCodec = Field(default="wav"),
        speech_sample_rate: CloneRate | None = Field(
            default=None, description="API default 24000. opus needs 8000/16000/24000/48000."
        ),
        enable_qc: bool | None = Field(
            default=None, description="Quality-control pass (API default false)."
        ),
        enable_vad: bool | None = Field(
            default=None, description="Trim silence (API default true)."
        ),
        remove_background_noise: bool | None = Field(
            default=None,
            description="Only with a reference clip; ignored with voice_id. API default false.",
        ),
        enable_text_normalization: bool | None = Field(default=None),
        min_audio_duration: float | None = Field(
            default=None, gt=0, description="Pad with silence up to N seconds."
        ),
        max_audio_duration: float | None = Field(
            default=None, gt=0, description="Time-stretch down to N seconds. Exclusive with pace."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        has_ref = ref_audio_path is not None or ref_audio_base64 is not None
        if (voice_id is not None) == has_ref:
            raise ValueError(
                "Provide exactly one of voice_id or a reference clip (ref_audio_path/ref_audio_base64)."
            )
        if pace is not None and max_audio_duration is not None:
            raise ValueError("pace and max_audio_duration are mutually exclusive.")
        if (
            min_audio_duration is not None
            and max_audio_duration is not None
            and max_audio_duration < min_audio_duration
        ):
            raise ValueError("max_audio_duration must be >= min_audio_duration.")
        if output_audio_codec == "opus" and speech_sample_rate not in (
            None,
            8000,
            16000,
            24000,
            48000,
        ):
            raise ValueError("opus requires speech_sample_rate 8000, 16000, 24000 or 48000.")

        def flag(v: bool) -> str:
            return str(v).lower()

        data: dict[str, Any] = {"text": text, "output_audio_codec": output_audio_codec}
        if voice_id:
            data["voice_id"] = voice_id
        if language_code:
            data["language_code"] = language_code
        if pace is not None:
            data["pace"] = pace
        if speech_sample_rate is not None:
            data["speech_sample_rate"] = speech_sample_rate
        for key, val in (
            ("enable_qc", enable_qc),
            ("enable_vad", enable_vad),
            ("remove_background_noise", remove_background_noise),
            ("enable_text_normalization", enable_text_normalization),
        ):
            if val is not None:
                data[key] = flag(val)
        if min_audio_duration is not None:
            data["min_audio_duration"] = min_audio_duration
        if max_audio_duration is not None:
            data["max_audio_duration"] = max_audio_duration

        with measure_tool() as metrics:
            if voice_id:
                # No file part: force multipart by sending every field as a (None, value) part.
                payload, call = await sc.client.post_multipart(
                    f"{VOICES_BASE}/clone", files={k: (None, str(v)) for k, v in data.items()}
                )
                metrics.merge(call)
            else:
                async with resolve_file_input(
                    file_path=ref_audio_path,
                    file_base64=ref_audio_base64,
                    filename=filename,
                    max_bytes=CLONE_REF_MAX_BYTES,
                ) as path:
                    with path.open("rb") as fh:
                        payload, call = await sc.client.post_multipart(
                            f"{VOICES_BASE}/clone",
                            data=data,
                            files={"ref_audio": (path.name, fh, _guess_audio_mime(path))},
                        )
                    metrics.merge(call)

        body = payload if isinstance(payload, dict) else {}
        audio_b64 = body.get("audio_b64") or body.get("audio")
        if not audio_b64:
            raise RuntimeError(f"Voice clone response had no audio. Raw: {body!r}")
        ext, mime = _CODEC_EXT[output_audio_codec]
        stored = await sc.audio_sink.store(
            base64.b64decode(audio_b64),
            filename=f"sarvam-voice-{uuid.uuid4().hex[:8]}.{ext}",
            mime_type=mime,
        )
        return {
            "file_path": stored.file_path,
            "resource_uri": stored.resource_uri,
            "base64_data": stored.base64_data,
            "mime_type": stored.mime_type,
            "size_bytes": stored.size_bytes,
            "audio_duration": body.get("audio_duration"),
            "request_id": body.get("request_id"),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_cloned_voice_list",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "List saved cloned voices (GET /voices), newest first. Filter with `search` (name "
            "substring), `gender`, `accent`; page with `limit` (default 50, max 200) and `offset`."
        ),
    )
    async def sarvam_voice_list(
        ctx: Context,
        search: str | None = Field(default=None),
        gender: str | None = Field(default=None, description="'male' or 'female'."),
        accent: str | None = Field(default=None),
        limit: int = Field(default=50, ge=1, le=200),
        offset: int = Field(default=0, ge=0),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for k, v in (("search", search), ("gender", gender), ("accent", accent)):
            if v:
                params[k] = v
        with measure_tool() as metrics:
            payload, call = await sc.client.get_json(VOICES_BASE, params=params)
            metrics.merge(call)
        data = payload.get("data") if isinstance(payload, dict) else None
        data = data if isinstance(data, dict) else {}
        return {
            "voices": data.get("voices", []),
            "total": data.get("total"),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_cloned_voice_get",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Get one cloned voice (GET /voices/{voice_id}): metadata, reference transcript, "
            "`noise_reduction_applied`, previews and time-limited signed audio URLs."
        ),
    )
    async def sarvam_voice_get(
        ctx: Context,
        voice_id: str = Field(description="Voice id (svc-…)."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.get_json(f"{VOICES_BASE}/{voice_id}")
            metrics.merge(call)
        body = payload if isinstance(payload, dict) else {}
        return {"voice": body.get("data"), "observability": metrics.to_response_block()}

    @mcp.tool(
        name="sarvam_tools_cloned_voice_delete",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Delete a cloned voice (DELETE /voices/delete/{voice_id}). Irreversible; frees a slot "
            "against the per-org voice cap. Confirm with the user before calling."
        ),
    )
    async def sarvam_voice_delete(
        ctx: Context,
        voice_id: str = Field(description="Voice id (svc-…) to delete."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            _, call = await sc.client.delete_json(f"{VOICES_BASE}/delete/{voice_id}")
            metrics.merge(call)
        return {"voice_id": voice_id, "deleted": True, "observability": metrics.to_response_block()}

    @mcp.tool(
        name="sarvam_tools_cloned_voice_watermark_detect",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Check whether audio carries Sarvam's watermark (POST /voices/watermark/detect, beta). "
            "WAV/MP3/FLAC/OGG/M4A/WebM, ≤10 MB, only the first 120 s analysed; clips under ~5 s "
            "are usually 'inconclusive'. verdict: watermarked | not_detected | inconclusive. "
            "Free (no credits) but limited to 5 requests/minute."
        ),
    )
    async def sarvam_voice_watermark_detect(
        ctx: Context,
        audio_path: str | None = Field(default=None),
        audio_base64: str | None = Field(default=None),
        audio_url: str | None = Field(default=None),
        filename: str | None = Field(
            default=None, description="Filename with extension for base64/URL input."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=audio_path,
            file_base64=audio_base64,
            file_url=audio_url,
            filename=filename,
            max_bytes=WATERMARK_MAX_BYTES,
        ) as path:
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    payload, call = await sc.client.post_multipart(
                        f"{VOICES_BASE}/watermark/detect",
                        files={"file": (path.name, fh, _guess_audio_mime(path))},
                    )
                metrics.merge(call)
        body = payload if isinstance(payload, dict) else {}
        info = body.get("data") if isinstance(body.get("data"), dict) else {}
        return {
            "verdict": info.get("verdict"),
            "z_score": info.get("z_score"),
            "analysed_seconds": info.get("analysed_seconds"),
            "inconclusive": info.get("inconclusive"),
            "details": info,
            "observability": metrics.to_response_block(),
        }
