"""Sarvam Vision — Document AI digitise and schema extract.

Both jobs are asynchronous:

  POST /doc-ai/v1/job/digitise   or   POST /doc-ai/v1/job/extract
  GET  /doc-ai/v1/job/{job_id}/status
  GET  /doc-ai/v1/job/{job_id}/download-url   (digitise)
  GET  /doc-ai/v1/job/{job_id}/results        (extract)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import ready_ctx, resolve_file_input

DOC_AI_BASE = "/doc-ai/v1/job"
DIGITISE_PATH = f"{DOC_AI_BASE}/digitise"
EXTRACT_PATH = f"{DOC_AI_BASE}/extract"

DigitiseFormat = Literal["md", "html", "json"]
ExtractFormat = Literal["json", "csv", "xlsx"]
DocumentContent = Literal["printed", "handwritten", "mixed"]

TERMINAL = {"completed", "partially_completed", "failed", "rejected"}
MAX_POLL_ATTEMPTS = 60
POLL_INTERVAL_SECONDS = 5


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_vision_digitise",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Digitise a document with Sarvam Vision (POST /doc-ai/v1/job/digitise). "
            "Full-document OCR that keeps layout, reading order, and tables. "
            "Output is markdown (`md`), HTML, or JSON.\n\n"
            "Uploads the file, polls until a terminal status, and returns the "
            "download URL. Max 10 pages. Use `language` (not language_code). "
            "Pass `md`, not `markdown`."
        ),
    )
    async def sarvam_vision_digitise(
        ctx: Context,
        document_path: str | None = Field(
            default=None,
            description="Local path to a PDF, PNG, JPEG, or ZIP. Max 10 pages.",
        ),
        document_base64: str | None = Field(
            default=None, description="Base64-encoded document (for remote MCP).",
        ),
        document_url: str | None = Field(
            default=None, description="URL to fetch the document from.",
        ),
        filename: str | None = Field(
            default=None,
            description="Filename with extension. Required for base64 or URL inputs.",
        ),
        output_format: DigitiseFormat = Field(
            default="md",
            description="'md', 'html', or 'json'. Do not pass 'markdown'.",
        ),
        language: str = Field(
            default="en-IN",
            description="BCP-47 language of the document, e.g. 'hi-IN'. Field name is language.",
        ),
        document_content: DocumentContent = Field(
            default="printed",
            description="'printed', 'handwritten', or 'mixed'.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        async with resolve_file_input(
            file_path=document_path,
            file_base64=document_base64,
            file_url=document_url,
            filename=filename,
        ) as path:
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    created, call = await sc.client.post_multipart(
                        DIGITISE_PATH,
                        data={
                            "language": language,
                            "output_format": output_format,
                            "content_type": document_content,
                            "model": "sarvam-vision-v1",
                        },
                        files={"file": (path.name, fh, _guess_doc_mime(path))},
                    )
                metrics.merge(call)
                job_id = created["job_id"]
                status = await _poll_job(ctx, sc, job_id, metrics)
                download = None
                if str(status.get("status", "")).lower() in {"completed", "partially_completed"}:
                    download, call = await sc.client.get_json(
                        f"{DOC_AI_BASE}/{job_id}/download-url"
                    )
                    metrics.merge(call)

        return {
            "job_id": job_id,
            "status": status.get("status"),
            "output_format": output_format,
            "usage": status.get("usage"),
            "download": download,
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_vision_extract",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Schema extraction with Sarvam Vision (POST /doc-ai/v1/job/extract). "
            "Pass a JSON schema (root type object, every field needs type and description) "
            "or a saved `config_id`. Returns structured fields from "
            "GET /doc-ai/v1/job/{job_id}/results.\n\n"
            "For full-document OCR to markdown or HTML, use sarvam_tools_vision_digitise."
        ),
    )
    async def sarvam_vision_extract(
        ctx: Context,
        document_path: str | None = Field(
            default=None,
            description="Local path to a PDF, PNG, JPEG, or ZIP. Max 10 pages.",
        ),
        document_base64: str | None = Field(
            default=None, description="Base64-encoded document (for remote MCP).",
        ),
        document_url: str | None = Field(
            default=None, description="URL to fetch the document from.",
        ),
        filename: str | None = Field(
            default=None,
            description="Filename with extension. Required for base64 or URL inputs.",
        ),
        schema: dict[str, Any] | None = Field(
            default=None,
            description=(
                "JSON schema object. Root must be type=object with properties. "
                "Each field needs type and a non-empty description. "
                "Provide this or config_id."
            ),
        ),
        config_id: str | None = Field(
            default=None,
            description="Saved extraction config. Provide this or schema.",
        ),
        language: str = Field(default="en-IN", description="BCP-47 document language."),
        output_format: ExtractFormat = Field(default="json"),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        if schema is None and not config_id:
            raise ValueError("Provide schema or config_id.")
        form: dict[str, Any] = {
            "language": language,
            "output_format": output_format,
            "model": "sarvam-vision-v1",
        }
        if schema is not None:
            form["schema"] = json.dumps(schema)
        if config_id:
            form["config_id"] = config_id

        async with resolve_file_input(
            file_path=document_path,
            file_base64=document_base64,
            file_url=document_url,
            filename=filename,
        ) as path:
            with measure_tool() as metrics:
                with path.open("rb") as fh:
                    created, call = await sc.client.post_multipart(
                        EXTRACT_PATH,
                        data=form,
                        files={"file": (path.name, fh, _guess_doc_mime(path))},
                    )
                metrics.merge(call)
                job_id = created["job_id"]
                status = await _poll_job(ctx, sc, job_id, metrics)
                results = None
                if str(status.get("status", "")).lower() in {
                    "completed",
                    "partially_completed",
                }:
                    results, call = await sc.client.get_json(
                        f"{DOC_AI_BASE}/{job_id}/results"
                    )
                    metrics.merge(call)

        return {
            "job_id": job_id,
            "status": status.get("status"),
            "usage": status.get("usage"),
            "result": (results or {}).get("result") if isinstance(results, dict) else results,
            "annotations": (results or {}).get("annotations") if isinstance(results, dict) else None,
            "raw": results,
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_vision_job_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll a Document AI job at GET /doc-ai/v1/job/{job_id}/status. "
            "Works for both digitise and extract. Terminal statuses: "
            "completed, partially_completed, failed, rejected."
        ),
    )
    async def sarvam_vision_job_status(
        ctx: Context,
        job_id: str = Field(description="Job id from vision_digitise or vision_extract."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            status, call = await sc.client.get_json(f"{DOC_AI_BASE}/{job_id}/status")
            metrics.merge(call)
        return {
            "job_id": job_id,
            "status": status.get("status"),
            "usage": status.get("usage"),
            "raw": status,
            "observability": metrics.to_response_block(),
        }


async def _poll_job(ctx: Context, sc: Any, job_id: str, metrics: Any) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for attempt in range(MAX_POLL_ATTEMPTS):
        status, call = await sc.client.get_json(f"{DOC_AI_BASE}/{job_id}/status")
        metrics.merge(call)
        state = str(status.get("status", "")).lower()
        if state in TERMINAL:
            return status
        if (attempt + 1) % 4 == 0:
            await ctx.report_progress(attempt + 1, MAX_POLL_ATTEMPTS)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"Document AI job {job_id} did not finish within "
        f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s. "
        "Poll with sarvam_tools_vision_job_status."
    )


def _guess_doc_mime(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "zip": "application/zip",
        "html": "text/html",
        "htm": "text/html",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(suffix, "application/octet-stream")
