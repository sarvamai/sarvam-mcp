"""Pronunciation Dictionary — CRUD for custom TTS pronunciation rules.

Pronunciation dictionaries let users define how specific words should be
pronounced in TTS output. All endpoints live under
``/text-to-speech/pronunciation-dictionary``.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import log_tool_error, ready_ctx

PRONDICT_BASE = "/text-to-speech/pronunciation-dictionary"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_pronunciation_list",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "List all pronunciation dictionary IDs owned by the authenticated user. "
            "Returns dictionary_count and a list of dictionary IDs."
        ),
    )
    async def sarvam_pronunciation_list(
        ctx: Context,
    ) -> dict[str, Any]:
        try:
            sc = await ready_ctx(ctx)
            with measure_tool() as metrics:
                payload, call = await sc.client.get_json(PRONDICT_BASE)
                metrics.merge(call)
            return {
                "dictionary_count": payload.get("dictionary_count", 0),
                "dictionaries": payload.get("dictionaries", []),
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_pronunciation_list", exc)
            raise

    @mcp.tool(
        name="sarvam_tools_pronunciation_get",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Retrieve a specific pronunciation dictionary by its ID. "
            "Returns the dictionary entries (word → pronunciation mappings)."
        ),
    )
    async def sarvam_pronunciation_get(
        ctx: Context,
        dictionary_id: str = Field(description="The pronunciation dictionary ID."),
    ) -> dict[str, Any]:
        try:
            sc = await ready_ctx(ctx)
            with measure_tool() as metrics:
                payload, call = await sc.client.get_json(
                    f"{PRONDICT_BASE}/{dictionary_id}"
                )
                metrics.merge(call)
            return {
                "dictionary_id": dictionary_id,
                "raw": payload,
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_pronunciation_get", exc)
            raise

    @mcp.tool(
        name="sarvam_tools_pronunciation_create",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Create a new pronunciation dictionary with word → pronunciation "
            "mappings. These dictionaries can be referenced in TTS calls to "
            "control how specific words are spoken.\n\n"
            "Max 100 words per dictionary, 10 dictionaries per user."
        ),
    )
    async def sarvam_pronunciation_create(
        ctx: Context,
        entries: dict[str, str] = Field(
            description=(
                "Word-to-pronunciation mappings: "
                "{'Sarvam': 'Saarvam', 'CEO': 'see ee oh'}."
            ),
        ),
        language_code: str = Field(
            default="hi-IN",
            description="BCP-47 language code for these entries, e.g. 'hi-IN', 'en-IN', 'ta-IN'.",
        ),
    ) -> dict[str, Any]:
        try:
            sc = await ready_ctx(ctx)
            dictionary = {"pronunciations": {language_code: entries}}
            dict_bytes = json.dumps(dictionary, ensure_ascii=False).encode("utf-8")
            with measure_tool() as metrics:
                payload, call = await sc.client.post_multipart(
                    PRONDICT_BASE,
                    files={"file": ("dictionary.json", dict_bytes, "application/json")},
                )
                metrics.merge(call)
            return {
                "raw": payload,
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_pronunciation_create", exc)
            raise

    @mcp.tool(
        name="sarvam_tools_pronunciation_delete",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Delete a pronunciation dictionary by its ID."
        ),
    )
    async def sarvam_pronunciation_delete(
        ctx: Context,
        dictionary_id: str = Field(description="The pronunciation dictionary ID to delete."),
    ) -> dict[str, Any]:
        try:
            sc = await ready_ctx(ctx)
            with measure_tool() as metrics:
                payload, call = await sc.client.delete_json(
                    PRONDICT_BASE, params={"dict_id": dictionary_id}
                )
                metrics.merge(call)
            return {
                "dictionary_id": dictionary_id,
                "deleted": True,
                "raw": payload,
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_pronunciation_delete", exc)
            raise
