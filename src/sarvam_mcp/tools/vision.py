"""Sarvam Vision — Document AI (job-based async pipeline).

Document AI (`/doc-ai/v1/job/...`) supersedes the earlier Document
Digitization API (`/doc-digitization/job/v1/...`) per Sarvam's Sept 2026
changelog. The new flow is a single multipart submission followed by polling
— no separate "get upload URLs" / blob PUT / "start" steps:
  1. Submit the file directly (POST /doc-ai/v1/job/digitise)
  2. Poll status    (GET  /doc-ai/v1/job/{job_id}/status)
  3. Get a download URL for the output (GET /doc-ai/v1/job/{job_id}/download-url)
  4. Download it — a ZIP containing the chosen output format, per-page
     metadata, and a manifest.

NOTE: this migration is based on docs.sarvam.ai as of 2026-09-15 and has not
been live-tested against the API (unlike most other endpoints in this repo,
which carry a "live-confirmed" date). Verify against a real account before
relying on it in production.

We expose two MCP tools:
  - sarvam_tools_vision_extract: orchestrates the full pipeline end-to-end
  - sarvam_tools_vision_job_status: poll an existing job
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

import httpx
from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, ready_ctx, resolve_file_input

DOC_JOB_BASE = "/doc-ai/v1/job"
DOC_DIGITISE_PATH = f"{DOC_JOB_BASE}/digitise"

OutputFormat = Literal["md", "html", "json"]

# Max 10 pages per the API docs.
MAX_POLL_ATTEMPTS = 60
POLL_INTERVAL_SECONDS = 3

TERMINAL_STATES = {"completed", "partially_completed", "failed", "rejected"}
SUCCESS_STATES = {"completed", "partially_completed"}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_vision_extract",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Extract text + structure from a document or image using Sarvam Vision "
            "(Document AI). Supports 23 Indian languages with table "
            "preservation. Outputs markdown (default), HTML, or JSON.\n\n"
            "This runs the full async pipeline: submit document → poll until "
            "complete → download output. Max 10 pages per document.\n\n"
            "Returns job metadata plus the downloaded output. The output is "
            "delivered as a ZIP file (saved locally) containing the chosen "
            "format plus per-page metadata."
        ),
    )
    async def sarvam_vision_extract(
        ctx: Context,
        document_path: str | None = Field(
            default=None, description="Local path to a PDF, image (png/jpg/jpeg), or ZIP.",
        ),
        document_base64: str | None = Field(
            default=None, description="Base64-encoded document data (for remote MCP).",
        ),
        document_url: str | None = Field(
            default=None, description="URL to fetch the document from.",
        ),
        filename: str | None = Field(
            default=None, description="Filename with extension (for base64/URL), e.g. 'invoice.pdf'.",
        ),
        output_format: OutputFormat = Field(
            default="md",
            description="Output format: 'md' (Markdown), 'html', or 'json'. Delivered as ZIP.",
        ),
        language_code: LanguageCode = Field(
            default="hi-IN",
            description="Primary language of the document (BCP-47). Helps optimize accuracy.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            async with resolve_file_input(
                file_path=document_path, file_base64=document_base64,
                file_url=document_url, filename=filename,
            ) as path:
                await ctx.info("Submitting document to Document AI…")
                with path.open("rb") as fh:
                    files = {"file": (path.name, fh, _guess_doc_mime(path))}
                    data: dict[str, Any] = {
                        "language": language_code if language_code != "unknown" else "hi-IN",
                        "output_format": output_format,
                    }
                    create_resp, call = await sc.client.post_multipart(
                        DOC_DIGITISE_PATH, data=data, files=files
                    )
                metrics.merge(call)
            job_id = create_resp["job_id"]

            # Poll for completion
            await ctx.info(f"Polling job {job_id}…")
            status_resp: dict[str, Any] = {}
            status = ""
            for attempt in range(MAX_POLL_ATTEMPTS):
                status_resp, call = await sc.client.get_json(f"{DOC_JOB_BASE}/{job_id}/status")
                metrics.merge(call)
                status = str(status_resp.get("status", "")).lower()
                if status in TERMINAL_STATES:
                    break
                if (attempt + 1) % 5 == 0:
                    await ctx.report_progress(attempt + 1, MAX_POLL_ATTEMPTS)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            else:
                return {
                    "job_id": job_id,
                    "status": status_resp.get("status", "timeout"),
                    "error": (
                        f"Job did not complete within "
                        f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s. "
                        f"Poll manually with sarvam_tools_vision_job_status."
                    ),
                    "observability": metrics.to_response_block(),
                }

            result: dict[str, Any] = {
                "job_id": job_id,
                "status": status_resp.get("status"),
                "output_format": output_format,
                "usage": status_resp.get("usage"),
                "raw_status": status_resp,
            }

            if status in SUCCESS_STATES:
                await ctx.info("Fetching output…")
                dl_resp, call = await sc.client.get_json(f"{DOC_JOB_BASE}/{job_id}/download-url")
                metrics.merge(call)
                dl_url = dl_resp.get("url")
                if dl_url:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as dl:
                        dl_http = await dl.get(dl_url)
                    if dl_http.is_success:
                        stored = await sc.audio_sink.store(
                            dl_http.content,
                            filename=f"sarvam-vision-{job_id}.zip",
                            mime_type="application/zip",
                        )
                        result["output_zip_path"] = stored.file_path
                        result["output_resource_uri"] = stored.resource_uri
                        result["output_size_bytes"] = stored.size_bytes

        result["observability"] = metrics.to_response_block()
        return result

    @mcp.tool(
        name="sarvam_tools_vision_job_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll the status of an existing Document AI job. Returns the "
            "current status and page usage. Once status is 'completed' or "
            "'partially_completed', a download URL for the output ZIP is "
            "included."
        ),
    )
    async def sarvam_vision_job_status(
        ctx: Context,
        job_id: str = Field(description="The job_id returned by sarvam_tools_vision_extract."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            status_resp, call = await sc.client.get_json(f"{DOC_JOB_BASE}/{job_id}/status")
            metrics.merge(call)

            result: dict[str, Any] = {
                "job_id": job_id,
                "status": status_resp.get("status"),
                "usage": status_resp.get("usage"),
                "raw": status_resp,
            }

            status = str(status_resp.get("status", "")).lower()
            if status in SUCCESS_STATES:
                dl_resp, call = await sc.client.get_json(f"{DOC_JOB_BASE}/{job_id}/download-url")
                metrics.merge(call)
                result["download_url"] = dl_resp.get("url")

        result["observability"] = metrics.to_response_block()
        return result


def _guess_doc_mime(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "tiff": "image/tiff",
        "zip": "application/zip",
    }.get(suffix, "application/octet-stream")
