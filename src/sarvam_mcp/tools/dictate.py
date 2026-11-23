"""Dictate — speech to clean, formatted text (``/v2/dictate``).

POST /v2/dictate               one clip, up to 30 s / 10,000,000 bytes, synchronous
POST /v2/dictate/jobs          long recordings (up to 1 hour), asynchronous
GET  /v2/dictate/jobs/{id}     poll a job (404 once expired, 7 days after completion)

Dictate differs from plain STT: it removes fillers, applies a style preset or
free-form rules, corrects names from a custom vocabulary, and can derive an
extra ``output`` (summary, JSON, an answer) from the whole recording.
Options travel as multipart form parts, each holding JSON text, never as
query parameters. Billed per minute of audio including silence.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import ready_ctx, resolve_file_input
from sarvam_mcp.tools.stt import _guess_audio_mime

DICTATE_PATH = "/v2/dictate"
DICTATE_JOBS_PATH = "/v2/dictate/jobs"

# /v2/dictate accepts at most 10,000,000 bytes of audio. Jobs accept far more
# (but the gateway answers 413 at roughly 100 MB), so uploads are capped there.
CLIP_MAX_BYTES = 10_000_000
JOB_MAX_BYTES = 100 * 1024 * 1024 - 1

# Dictate spells Odia `or-IN` and uses `auto` (not `unknown`) for detection.
DictateLanguage = Literal[
    "auto",
    "hi-IN",
    "bn-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "or-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
    "en-IN",
    "gu-IN",
    "as-IN",
    "ur-IN",
    "ne-IN",
    "kok-IN",
    "ks-IN",
    "sd-IN",
    "sa-IN",
    "sat-IN",
    "mni-IN",
    "brx-IN",
    "mai-IN",
    "doi-IN",
]
DictateMode = Literal["transcribe", "verbatim", "translit", "codemix"]
StylePreset = Literal["none", "light", "clean"]


def _form_parts(
    *,
    language_code: str | None,
    mode: str | None,
    style_preset: str | None,
    style_rules: str | None,
    vocabulary: list[dict[str, Any]] | None,
    context_text: str | None,
    context_reference: str | None,
    output_rules: str | None,
    model: str | None,
) -> dict[str, str]:
    """Build the optional form parts. Empty strings are rejected by the API
    (400), so only parts that carry a value are included."""
    parts: dict[str, str] = {}
    if language_code:
        parts["language_code"] = language_code
    if mode:
        parts["mode"] = mode
    if style_preset or style_rules:
        style: dict[str, Any] = {}
        if style_preset:
            style["preset"] = style_preset
        if style_rules:
            style["rules"] = style_rules
        parts["style"] = json.dumps(style, ensure_ascii=False)
    if vocabulary:
        for entry in vocabulary:
            if not isinstance(entry, dict) or not entry.get("word"):
                raise ValueError("Each vocabulary entry needs a non-empty 'word'.")
            if set(entry) - {"word", "sounds_like", "description"}:
                raise ValueError(
                    "vocabulary entries accept only word, sounds_like (list) and description."
                )
        parts["vocabulary"] = json.dumps(vocabulary, ensure_ascii=False)
    if context_text or context_reference:
        context: dict[str, Any] = {}
        if context_text:
            context["text"] = context_text
        if context_reference:
            context["reference"] = context_reference
        parts["context"] = json.dumps(context, ensure_ascii=False)
    if output_rules and output_rules.strip():
        parts["output_rules"] = output_rules
    if model:
        parts["model"] = model
    return parts


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_dictate_clip",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Dictate a short clip (≤30 s, ≤10 MB) into clean, formatted text with POST /v2/dictate. "
            "Unlike sarvam_tools_stt_transcribe it removes fillers, applies a style "
            "(`style_preset` none|light|clean and/or free-form `style_rules`), fixes names "
            "from `vocabulary`, and can derive an extra `output` (summary / JSON / answer) "
            "from `output_rules`. For longer audio use sarvam_tools_dictate_job_submit.\n\n"
            "Billed per minute of audio, silence included. Degraded results are not billed."
        ),
    )
    async def sarvam_dictate_clip(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to the audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio."),
        audio_url: str | None = Field(default=None, description="URL to fetch the audio from."),
        filename: str | None = Field(
            default=None, description="Filename with extension. Required for base64/URL inputs."
        ),
        language_code: DictateLanguage | None = Field(
            default=None, description="BCP-47 code or 'auto'. Odia is 'or-IN'. Omit to auto-detect."
        ),
        mode: DictateMode | None = Field(
            default=None,
            description="transcribe (default) | verbatim | translit | codemix. There is no translate mode.",
        ),
        style_preset: StylePreset | None = Field(
            default=None,
            description="none | light | clean. Default: light for verbatim mode, clean otherwise.",
        ),
        style_rules: str | None = Field(
            default=None,
            max_length=2000,
            description="Free-form formatting rules, e.g. 'Write numbers as digits. Use bullet points.'",
        ),
        vocabulary: list[dict[str, Any]] | None = Field(
            default=None,
            description=(
                "Names/terms to get right (max 1000). Each: {'word': str (1-64 chars), "
                "'sounds_like': [up to 5 strings], 'description': str (max 200)}."
            ),
        ),
        context_text: str | None = Field(
            default=None,
            max_length=2000,
            description="Short note about the recording (who/what/where).",
        ),
        context_reference: str | None = Field(
            default=None,
            max_length=50000,
            description="Reference text (up to 50,000 chars) to spell names/terms from.",
        ),
        output_rules: str | None = Field(
            default=None,
            max_length=4000,
            description="Makes an extra `output` from the whole recording, e.g. 'Summarise in 3 bullets'.",
        ),
        model: str | None = Field(
            default=None,
            description="Pin a snapshot, e.g. 'dictate-v1-2026-11-04'. Default 'dictate-v1' (alias "
            "of the latest).",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        parts = _form_parts(
            language_code=language_code,
            mode=mode,
            style_preset=style_preset,
            style_rules=style_rules,
            vocabulary=vocabulary,
            context_text=context_text,
            context_reference=context_reference,
            output_rules=output_rules,
            model=model,
        )
        async with resolve_file_input(
            file_path=audio_path,
            file_base64=audio_base64,
            file_url=audio_url,
            filename=filename,
            max_bytes=CLIP_MAX_BYTES,
        ) as path:
            if path.stat().st_size > CLIP_MAX_BYTES:
                raise ValueError(
                    "Clip is over 10,000,000 bytes — use sarvam_tools_dictate_job_submit for long audio."
                )
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    payload, call = await sc.client.post_multipart(
                        DICTATE_PATH,
                        data=parts,
                        files={"file": (path.name, fh, _guess_audio_mime(path))},
                    )
                metrics.merge(call)

        body = payload if isinstance(payload, dict) else {}
        return {
            "text": body.get("text"),
            "transcript": body.get("transcript"),
            "language_code": body.get("language_code"),
            "corrections": body.get("corrections"),
            "degraded": body.get("degraded"),
            "output": body.get("output"),
            "usage": body.get("usage"),
            "model": body.get("model"),
            "request_id": body.get("request_id"),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_dictate_job_submit",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Start an asynchronous Dictate job (POST /v2/dictate/jobs) for recordings up to 1 hour. "
            "Provide a local file/base64 (under ~100 MB) or an `audio_url` (https, port 443/8443, "
            "no private addresses) — never both. Returns a job_id; poll with "
            "sarvam_tools_dictate_job_status (every 5 s or slower). Each call creates a new "
            "billed job — there is no idempotency key, so do not retry blindly."
        ),
    )
    async def sarvam_dictate_job_submit(
        ctx: Context,
        audio_path: str | None = Field(default=None, description="Local path to the audio file."),
        audio_base64: str | None = Field(default=None, description="Base64-encoded audio."),
        audio_url: str | None = Field(
            default=None,
            description="https URL the service fetches itself (use for files ~100 MB or larger).",
        ),
        filename: str | None = Field(
            default=None, description="Filename with extension for base64 input."
        ),
        language_code: DictateLanguage | None = Field(default=None),
        mode: DictateMode | None = Field(default=None),
        style_preset: StylePreset | None = Field(default=None),
        style_rules: str | None = Field(default=None, max_length=2000),
        vocabulary: list[dict[str, Any]] | None = Field(
            default=None, description="Same shape as the clip tool."
        ),
        context_text: str | None = Field(default=None, max_length=2000),
        context_reference: str | None = Field(default=None, max_length=50000),
        output_rules: str | None = Field(default=None, max_length=4000),
        model: str | None = Field(default=None),
        callback_url: str | None = Field(
            default=None,
            description="https webhook (port 443/8443, no redirects) called when the job ends.",
        ),
        callback_auth_token: str | None = Field(
            default=None,
            description="Sent back in the X-SARVAM-JOB-CALLBACK-TOKEN header (1-4096 "
            "printable ASCII).",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        sources = sum(x is not None for x in (audio_path, audio_base64, audio_url))
        if sources != 1:
            raise ValueError("Provide exactly one of audio_path, audio_base64 or audio_url.")
        if callback_auth_token and not callback_url:
            raise ValueError("callback_auth_token needs callback_url.")
        parts = _form_parts(
            language_code=language_code,
            mode=mode,
            style_preset=style_preset,
            style_rules=style_rules,
            vocabulary=vocabulary,
            context_text=context_text,
            context_reference=context_reference,
            output_rules=output_rules,
            model=model,
        )
        if callback_url:
            callback: dict[str, str] = {"url": callback_url}
            if callback_auth_token:
                callback["auth_token"] = callback_auth_token
            parts["callback"] = json.dumps(callback)

        with measure_tool() as metrics:
            if audio_url:
                parts["audio_url"] = audio_url
                # No file part: send every field as a multipart part ((None, value))
                # so the request is multipart/form-data, not url-encoded.
                payload, call = await sc.client.post_multipart(
                    DICTATE_JOBS_PATH, files={k: (None, v) for k, v in parts.items()}
                )
                metrics.merge(call)
            else:
                async with resolve_file_input(
                    file_path=audio_path,
                    file_base64=audio_base64,
                    filename=filename,
                    max_bytes=JOB_MAX_BYTES,
                ) as path:
                    if path.stat().st_size > JOB_MAX_BYTES:
                        raise ValueError(
                            "File is ~100 MB or larger; host it and pass audio_url instead."
                        )
                    with path.open("rb") as fh:
                        payload, call = await sc.client.post_multipart(
                            DICTATE_JOBS_PATH,
                            data=parts,
                            files={"file": (path.name, fh, _guess_audio_mime(path))},
                        )
                    metrics.merge(call)

        body = payload if isinstance(payload, dict) else {}
        return {
            "job_id": body.get("job_id"),
            "job_state": body.get("job_state"),
            "next_steps": "Poll sarvam_tools_dictate_job_status(job_id) every 5 s or slower.",
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_dictate_job_delete",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Delete a Dictate job and its stored result (DELETE /v2/dictate/jobs/{job_id}). "
            "Irreversible — confirm with the user first. Jobs also expire on their own 7 days "
            "after completion."
        ),
    )
    async def sarvam_dictate_job_delete(
        ctx: Context,
        job_id: str = Field(description="Job id from sarvam_tools_dictate_job_submit."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.delete_json(f"{DICTATE_JOBS_PATH}/{job_id}")
            metrics.merge(call)
        return {
            "job_id": job_id,
            "deleted": True,
            "raw": payload if isinstance(payload, dict) else None,
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_dictate_job_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll GET /v2/dictate/jobs/{job_id}. job_state: Accepted, Pending, Running, "
            "Completed, Failed (a failed job still returns HTTP 200 with `error`). Results "
            "are kept 7 days after completion, then the job returns 404."
        ),
    )
    async def sarvam_dictate_job_status(
        ctx: Context,
        job_id: str = Field(description="Job id from sarvam_tools_dictate_job_submit."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.get_json(f"{DICTATE_JOBS_PATH}/{job_id}")
            metrics.merge(call)
        body = payload if isinstance(payload, dict) else {}
        result = body.get("result") if isinstance(body.get("result"), dict) else None
        return {
            "job_id": body.get("job_id", job_id),
            "job_state": body.get("job_state"),
            "created_at": body.get("created_at"),
            "completed_at": body.get("completed_at"),
            "expires_at": body.get("expires_at"),
            "error": body.get("error"),
            "text": result.get("text") if result else None,
            "result": result,
            "observability": metrics.to_response_block(),
        }
