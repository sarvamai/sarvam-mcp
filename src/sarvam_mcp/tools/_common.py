"""Shared types + helpers used across tool modules.

Keeps language enums, speaker enums, and tool-context lookup in one place
so tool modules can stay short and focused on their endpoint shape.
"""

from __future__ import annotations

import base64
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastmcp import Context

from sarvam_mcp._registry import ServerContext

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


@asynccontextmanager
async def resolve_file_input(
    *,
    file_path: str | None = None,
    file_base64: str | None = None,
    file_url: str | None = None,
    filename: str | None = None,
    max_bytes: int = MAX_FILE_BYTES,
) -> AsyncIterator[Path]:
    """Resolve a file from a local path, base64 data, or URL into a ``Path``.

    Exactly one of ``file_path``, ``file_base64``, or ``file_url`` must be set.
    For base64/URL inputs a temporary file is created and cleaned up on exit.
    ``filename`` preserves the extension for MIME detection (required when not
    using ``file_path``).
    """
    provided = sum(x is not None for x in (file_path, file_base64, file_url))
    if provided != 1:
        raise ValueError(
            "Provide exactly one of: file path, base64 data, or URL. "
            f"Got {provided}."
        )

    if file_path is not None:
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        yield path
        return

    suffix = ""
    if filename:
        suffix = Path(filename).suffix or ""

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    try:
        if file_base64 is not None:
            data = base64.b64decode(file_base64)
            if len(data) > max_bytes:
                raise ValueError(
                    f"Decoded file is {len(data)} bytes, exceeds {max_bytes} byte limit."
                )
            tmp.write(data)
            tmp.close()
            yield tmp_path
        else:
            assert file_url is not None
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                async with client.stream("GET", file_url) as resp:
                    resp.raise_for_status()
                    downloaded = 0
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            raise ValueError(
                                f"Downloaded file exceeds {max_bytes} byte limit."
                            )
                        tmp.write(chunk)
            tmp.close()
            yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)

# ---- Language codes -------------------------------------------------------
#
# Sarvam uses BCP-47-style codes with the ISO 639-3 language subtag for
# constitutionally-listed languages.
# Auto-detect: the Translate/Transliterate APIs accept ``"auto"``; STT
# accepts ``"unknown"``.  Both values are exposed so the agent can use
# either; tool implementations map to the value the upstream endpoint
# expects before calling the API.

LanguageCode = Literal[
    "en-IN",  # English
    "hi-IN",  # Hindi
    "bn-IN",  # Bengali
    "ta-IN",  # Tamil
    "te-IN",  # Telugu
    "gu-IN",  # Gujarati
    "kn-IN",  # Kannada
    "ml-IN",  # Malayalam
    "mr-IN",  # Marathi
    "pa-IN",  # Punjabi
    "od-IN",  # Odia
    "as-IN",  # Assamese
    "ur-IN",  # Urdu
    "ne-IN",  # Nepali
    "kok-IN",  # Konkani
    "ks-IN",  # Kashmiri
    "sd-IN",  # Sindhi
    "sa-IN",  # Sanskrit
    "sat-IN",  # Santali
    "mni-IN",  # Manipuri
    "brx-IN",  # Bodo
    "mai-IN",  # Maithili
    "doi-IN",  # Dogri
    "auto",  # Auto-detect (Translate / Transliterate APIs)
    "unknown",  # Auto-detect (STT API, kept for backward compat)
]

# Subset of languages with TTS voices (bulbul:v3 / bulbul:v4-flash). STT covers all 23 above.
TtsLanguageCode = Literal[
    "en-IN",
    "hi-IN",
    "bn-IN",
    "ta-IN",
    "te-IN",
    "gu-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "pa-IN",
    "od-IN",
]


# ---- TTS models + speakers -------------------------------------------------
#
# Speaker IDs are model-specific: bulbul:v3 uses short names (``shubh``,
# ``priya``); bulbul:v4-flash uses persona IDs (``simran_en_customer``). The
# API rejects a mismatch with an error that lists the valid speakers, so the
# speaker is a plain string rather than a Literal. Rosters live in
# ``sarvam_mcp.code._data`` and are served by ``sarvam_code_speakers``.
# Default stays bulbul:v3 so existing callers (and their v3 speaker names)
# keep working; pass ``model="bulbul:v4-flash"`` to opt in.

TtsModel = Literal["bulbul:v3", "bulbul:v4-flash"]
DEFAULT_TTS_MODEL: TtsModel = "bulbul:v3"
DEFAULT_TTS_SPEAKERS: dict[str, str] = {
    "bulbul:v3": "shubh",
    "bulbul:v4-flash": "shubh_enhi_ads",
}


def resolve_tts_speaker(model: str, speaker: str | None) -> str:
    """The caller's speaker, or the model's documented default."""
    return speaker or DEFAULT_TTS_SPEAKERS.get(model, DEFAULT_TTS_SPEAKERS[DEFAULT_TTS_MODEL])


# Chat completions — same IDs as ``sarvam_tools_llm_complete``.
# sarvam-30b and sarvam-m were deprecated by Sarvam. Both remaining IDs are
# served on /v1/chat/completions: sarvam-105b (128K ctx, complex reasoning/
# agentic/coding) and sarvam-105b-conversations (32K ctx, post-trained for
# real-time dialogue and voice-agent workloads — same price, same schema).
SarvamLLM = Literal["sarvam-105b", "sarvam-105b-conversations"]


# ---- Translate-mode + script enums ---------------------------------------

TranslateMode = Literal["formal", "modern-colloquial", "classic-colloquial", "code-mixed"]
OutputScript = Literal["roman", "fully-native", "spoken-form-in-native"]
NumeralsFormat = Literal["international", "native"]
SpeakerGender = Literal["Male", "Female"]


# ---- Server context lookup -----------------------------------------------


def server_ctx(ctx: Context) -> ServerContext:
    """Pull the lifespan-managed ServerContext off a tool ``Context``.

    Sync — does NOT verify auth. Use ``await ready_ctx(ctx)`` from any tool
    function that needs to make API calls.
    """
    lifespan = ctx.request_context.lifespan_context
    if not isinstance(lifespan, ServerContext):
        raise RuntimeError(
            "Lifespan context is not a ServerContext — server.py wiring is broken."
        )
    return lifespan


async def ready_ctx(ctx: Context) -> ServerContext:
    """Pull the ServerContext + ensure auth is set (eliciting from the client
    if necessary). Every tool that calls the Sarvam API should ``await`` this
    on its first line.
    """
    from sarvam_mcp.auth.elicit import ensure_auth  # lazy to avoid circular import

    await ensure_auth(ctx)
    return server_ctx(ctx)
