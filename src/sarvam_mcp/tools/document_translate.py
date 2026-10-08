"""Document translation — whole files, layout preserved.

POST /translate/document/jobs
PUT  {upload_url}
POST /translate/document/jobs/{job_id}/start
GET  /translate/document/jobs/{job_id}/live-status
POST /translate/document/jobs/{job_id}/export?lang=
GET  /translate/document/jobs/{job_id}/export/status
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import ready_ctx
from sarvam_mcp.tools._uploads import presigned_put_headers
from sarvam_mcp.tools.vision import _guess_doc_mime

DOC_TRANSLATE_BASE = "/translate/document/jobs"
Genre = Literal[
    "NON_FICTION",
    "ADULT_FICTION",
    "CHILDREN_FICTION",
    "RELIGIOUS",
    "LEGAL",
    "ACADEMIC",
]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_document_translate",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Translate a whole document (PDF, Word, Excel, PowerPoint, HTML) "
            "via POST /translate/document/jobs. Layout is preserved. "
            "Up to 12 target languages.\n\n"
            "Creates the job, uploads the file to the signed URL, and starts it. "
            "Poll with sarvam_tools_document_translate_status. This is not "
            "sarvam_tools_translate (plain text) or sarvam_tools_localize (string tables)."
        ),
    )
    async def sarvam_document_translate(
        ctx: Context,
        document_path: str = Field(description="Absolute path to the source document."),
        source_language_code: str = Field(description="BCP-47 source language, e.g. en-IN."),
        target_language_codes: list[str] = Field(
            description="1 to 12 BCP-47 target language codes.",
        ),
        genre: Genre | None = Field(default=None),
        job_name: str | None = Field(default=None),
        use_native_numerals: bool = Field(default=False),
        style_guidelines: str | None = Field(
            default=None, description="Tone or terminology notes, up to about 4000 characters."
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        path = Path(document_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Document not found: {path}")
        if not 1 <= len(target_language_codes) <= 12:
            raise ValueError("target_language_codes must contain 1 to 12 languages.")

        body: dict[str, Any] = {
            "source_language_code": source_language_code,
            "target_language_codes": target_language_codes,
            "original_filename": path.name,
            "use_native_numerals": use_native_numerals,
        }
        if genre:
            body["genre"] = genre
        if job_name:
            body["job_name"] = job_name
        if style_guidelines:
            body["style_guidelines"] = style_guidelines

        with measure_tool() as metrics:
            created, call = await sc.client.post_json(DOC_TRANSLATE_BASE, json_body=body)
            metrics.merge(call)
            job_id = created["job_id"]
            upload_url = created.get("upload_url")
            if not upload_url:
                raise RuntimeError(f"Document translation job returned no upload_url: {created!r}")
            await ctx.info(f"Uploading {path.name} for job {job_id}…")
            await sc.client.put_external(
                upload_url,
                path.read_bytes(),
                headers=presigned_put_headers(_guess_doc_mime(path), azure=True),
            )
            started, call = await sc.client.post_json(
                f"{DOC_TRANSLATE_BASE}/{job_id}/start", json_body={}
            )
            metrics.merge(call)

        return {
            "job_id": job_id,
            "source_language_code": source_language_code,
            "target_language_codes": target_language_codes,
            "start": started,
            "next_steps": (
                "Poll sarvam_tools_document_translate_status(job_id). "
                "When a language state is Completed, call it again with export=true."
            ),
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_document_translate_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll GET /translate/document/jobs/{job_id}/live-status. "
            "job_state is Accepted, Running, Completed, PartiallyCompleted, or Failed.\n\n"
            "Set export=true once a target language is Completed to enqueue "
            "POST .../export and return signed download URLs."
        ),
    )
    async def sarvam_document_translate_status(
        ctx: Context,
        job_id: str = Field(description="Job id from sarvam_tools_document_translate."),
        export: bool = Field(
            default=False,
            description="When true, export every language whose state is Completed and return download URLs.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        downloads: dict[str, Any] = {}
        with measure_tool() as metrics:
            status, call = await sc.client.get_json(
                f"{DOC_TRANSLATE_BASE}/{job_id}/live-status"
            )
            metrics.merge(call)
            if export:
                for item in status.get("translations") or []:
                    if not isinstance(item, dict) or item.get("state") != "Completed":
                        continue
                    lang = item.get("target_language_code")
                    if not isinstance(lang, str):
                        continue
                    triggered, call = await sc.client.post_json(
                        f"{DOC_TRANSLATE_BASE}/{job_id}/export?lang={lang}",
                        json_body={},
                    )
                    metrics.merge(call)
                    export_id = triggered.get("export_id")
                    query = f"export_id={export_id}" if export_id else f"lang={lang}"
                    exported: dict[str, Any] = {}
                    for _ in range(6):
                        exported, call = await sc.client.get_json(
                            f"{DOC_TRANSLATE_BASE}/{job_id}/export/status?{query}"
                        )
                        metrics.merge(call)
                        if exported.get("export_state") in {"Completed", "Failed"}:
                            break
                        await asyncio.sleep(5)
                    downloads[lang] = {
                        "export_state": exported.get("export_state"),
                        "download_url": exported.get("download_url"),
                        "filename": exported.get("filename"),
                    }

        return {
            "job_id": job_id,
            "job_state": status.get("job_state"),
            "progress": status.get("progress"),
            "translations": status.get("translations"),
            "error_message": status.get("error_message"),
            "downloads": downloads,
            "raw": status,
            "observability": metrics.to_response_block(),
        }
