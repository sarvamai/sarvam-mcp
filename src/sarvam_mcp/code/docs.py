"""``sarvam_code_*`` documentation tools.

Five tools exposed:
  - sarvam_code_search_docs    — full-text search across docs.sarvam.ai
  - sarvam_code_api_reference  — endpoint shapes (params, response, gotchas)
  - sarvam_code_languages      — supported language codes per API
  - sarvam_code_speakers       — TTS speakers per model tag
  - sarvam_code_pricing        — current pricing structure

Source-of-truth data lives in ``code/_data.py``; the search tool fetches
``docs.sarvam.ai/llms-full.txt`` lazily through ``code/source.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from sarvam_mcp.code import _data
from sarvam_mcp.code.index import chunk_docs, search
from sarvam_mcp.code.source import fetch_docs

# Stable for the life of the process. First call lazily populates.
_INDEX_CACHE: list = []


async def _get_index() -> list:
    if not _INDEX_CACHE:
        text = await fetch_docs()
        _INDEX_CACHE.extend(chunk_docs(text))
    return _INDEX_CACHE


# ---- Type literals -------------------------------------------------------

ApiName = Literal[
    "stt", "stt_translate", "tts", "translate", "transliterate",
    "lid", "llm", "vision",
]
EndpointPath = Literal[
    "/speech-to-text",
    "/speech-to-text-translate",
    "/speech-to-text/job/init",
    "/text-to-speech",
    "/translate",
    "/transliterate",
    "/text-lid",
    "/text-analytics",
    "/v1/chat/completions",
    "/doc-digitization/job/v1",
    "/text-to-speech/pronunciation-dictionary",
]
TtsModel = Literal["bulbul:v3", "bulbul:v3-beta"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_code_search_docs",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Search Sarvam's developer docs (docs.sarvam.ai). Use this when "
            "you're writing code that calls Sarvam APIs and need to look up "
            "endpoint behavior, error codes, or model details. Returns the "
            "top matching sections with snippets and URLs."
        ),
    )
    async def sarvam_code_search_docs(
        query: str = Field(description="Plain-text search query, e.g. 'streaming TTS', 'language codes'."),
        limit: int = Field(default=5, ge=1, le=20),
    ) -> dict[str, Any]:
        chunks = await _get_index()
        hits = search(chunks, query, limit=limit)
        return {
            "query": query,
            "results": [
                {
                    "section": hit.chunk.heading,
                    "level": hit.chunk.level,
                    "url": hit.chunk.url,
                    "snippet": hit.snippet,
                    "score": round(hit.score, 3),
                }
                for hit in hits
            ],
            "result_count": len(hits),
        }

    @mcp.tool(
        name="sarvam_code_api_reference",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Return the authoritative request/response shape for a Sarvam "
            "API endpoint — parameters, defaults, content type, auth header, "
            "common gotchas. Faster + more accurate than free-text doc "
            "search when the agent already knows which endpoint to use."
        ),
    )
    def sarvam_code_api_reference(
        endpoint: EndpointPath = Field(description="The Sarvam API path, e.g. '/text-to-speech'."),
    ) -> dict[str, Any]:
        ref = _data.API_REFERENCE.get(endpoint)
        if not ref:
            return {
                "endpoint": endpoint,
                "found": False,
                "note": "Unknown endpoint. Available: " + ", ".join(sorted(_data.API_REFERENCE.keys())),
            }
        return {
            "endpoint": endpoint,
            "found": True,
            **ref,
        }

    @mcp.tool(
        name="sarvam_code_languages",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "List supported BCP-47 language codes for a given Sarvam API. "
            "Critical because coverage varies by API: STT supports 23 langs, "
            "TTS supports 11, etc. Returns code + display name + script."
        ),
    )
    def sarvam_code_languages(
        api: ApiName = Field(description="Which Sarvam API. STT covers 23; TTS covers 11."),
    ) -> dict[str, Any]:
        langs = _data.LANGUAGES_BY_API.get(api, [])
        return {
            "api": api,
            "language_count": len(langs),
            "languages": langs,
        }

    @mcp.tool(
        name="sarvam_code_speakers",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "List TTS speakers compatible with a given model tag. The v3 roster "
            "has 38 voices. Returns each speaker with a brief tone hint where available."
        ),
    )
    def sarvam_code_speakers(
        model: TtsModel = Field(default="bulbul:v3"),
    ) -> dict[str, Any]:
        ids = _data.SPEAKERS_BY_MODEL.get(model, [])
        return {
            "model": model,
            "speaker_count": len(ids),
            "speakers": [
                {"id": s, "tone": _data.SPEAKER_HINTS.get(s, "")}
                for s in ids
            ],
        }

    @mcp.tool(
        name="sarvam_code_pricing",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Current pricing structure for a Sarvam model (or all models if "
            "omitted). Returns billing unit + rate tier. NOTE: this is a "
            "high-level structure; exact per-unit rates depend on your plan "
            "— always confirm at https://dashboard.sarvam.ai before quoting."
        ),
    )
    def sarvam_code_pricing(
        model: str | None = Field(
            default=None,
            description="Specific model id, e.g. 'bulbul:v3'. Omit to list all.",
        ),
    ) -> dict[str, Any]:
        if model:
            entry = _data.PRICING.get(model)
            if not entry:
                return {
                    "model": model,
                    "found": False,
                    "available_models": sorted(_data.PRICING.keys()),
                    "disclaimer": _data.PRICING_DISCLAIMER,
                }
            return {
                "model": model,
                "found": True,
                **entry,
                "disclaimer": _data.PRICING_DISCLAIMER,
            }
        return {
            "models": _data.PRICING,
            "disclaimer": _data.PRICING_DISCLAIMER,
        }
