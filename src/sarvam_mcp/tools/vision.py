"""Sarvam Vision — Document Intelligence (job-based async pipeline).

The Document Intelligence API is a multi-step pipeline:
  1. Create a job  (POST /doc-digitization/job/v1)
  2. Get upload URLs (POST /doc-digitization/job/v1/upload-files)
  3. Upload the file to the presigned URL (PUT to Azure/GCS SAS URL)
  4. Start the job  (POST /doc-digitization/job/v1/{job_id}/start)
  5. Poll status    (GET  /doc-digitization/job/v1/{job_id}/status)
  6. Download output from the presigned output URL

We expose two MCP tools:
  - sarvam_tools_vision_extract: orchestrates the full pipeline end-to-end
  - sarvam_tools_vision_job_status: poll an existing job
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, ready_ctx, resolve_file_input

DOC_JOB_BASE = "/doc-digitization/job/v1"
DOC_JOB_UPLOAD = f"{DOC_JOB_BASE}/upload-files"

OutputFormat = Literal["md", "html", "json"]

# Max 10 pages per the API docs.
MAX_POLL_ATTEMPTS = 60
POLL_INTERVAL_SECONDS = 3


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_vision_extract",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Extract text + structure from a document or image using Sarvam Vision "
            "(Document Intelligence). Supports 23 Indian languages with table "
            "preservation. Outputs markdown (default), HTML, or JSON.\n\n"
            "This runs the full async pipeline: create job → upload file → "
            "start → poll until complete. Max 10 pages per document.\n\n"
            "Returns the output download URL (presigned) and job metadata. "
            "The output is delivered as a ZIP file containing the chosen format "
            "plus a JSON file with page-level data."
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
        async with resolve_file_input(
            file_path=document_path, file_base64=document_base64,
            file_url=document_url, filename=filename,
        ) as path:
            with measure_tool() as metrics:
                # Step 1: Create the job
                await ctx.info("Creating Document Intelligence job…")
                create_body: dict[str, Any] = {
                    "job_parameters": {
                        "language": language_code if language_code not in ("auto", "unknown") else "hi-IN",
                        "output_format": output_format,
                    },
                }
                create_resp, call = await sc.client.post_json(
                    DOC_JOB_BASE, json_body=create_body
                )
                metrics.merge(call)
                job_id = create_resp["job_id"]

                # Step 2: Get upload URLs
                await ctx.info(f"Getting upload URL for job {job_id}…")
                upload_req: dict[str, Any] = {
                    "job_id": job_id,
                    "files": [path.name],
                }
                upload_resp, call = await sc.client.post_json(
                    DOC_JOB_UPLOAD, json_body=upload_req
                )
                metrics.merge(call)

                upload_urls = upload_resp.get("upload_urls", {})
                if not upload_urls:
                    raise RuntimeError(f"No upload URLs returned for job {job_id}")

                # Step 3: Upload file to the presigned URL
                await ctx.info("Uploading document…")
                file_details = next(iter(upload_urls.values()))
                presigned_url = file_details["file_url"]
                file_metadata = file_details.get("file_metadata") or {}

                extra_headers = {str(k): str(v) for k, v in file_metadata.items()}
                with path.open("rb") as fh:
                    blob_metrics = await sc.client.put_blob(
                        presigned_url,
                        fh.read(),
                        content_type=_guess_doc_mime(path),
                        extra_headers=extra_headers,
                    )
                metrics.merge(blob_metrics)

                # Step 4: Start the job
                await ctx.info("Starting processing…")
                start_resp, call = await sc.client.post_json(
                    f"{DOC_JOB_BASE}/{job_id}/start", json_body={}
                )
                metrics.merge(call)

                # Step 5: Poll for completion
                await ctx.info("Polling for completion…")
                terminal_states = {"Completed", "PartiallyCompleted", "Failed"}
                status_resp: dict[str, Any] = {}
                for attempt in range(MAX_POLL_ATTEMPTS):
                    status_resp, call = await sc.client.get_json(
                        f"{DOC_JOB_BASE}/{job_id}/status"
                    )
                    metrics.merge(call)
                    job_state = status_resp.get("job_state", "")
                    if job_state in terminal_states:
                        break
                    if (attempt + 1) % 5 == 0:
                        await ctx.report_progress(attempt + 1, MAX_POLL_ATTEMPTS)
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                else:
                    return {
                        "job_id": job_id,
                        "job_state": status_resp.get("job_state", "timeout"),
                        "error": (
                            f"Job did not complete within "
                            f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s. "
                            f"Poll manually with sarvam_tools_vision_job_status."
                        ),
                        "observability": metrics.to_response_block(),
                    }

        return {
            "job_id": job_id,
            "job_state": status_resp.get("job_state"),
            "output_format": output_format,
            "page_metrics": status_resp.get("page_metrics"),
            "output_storage_path": status_resp.get("output_storage_path"),
            "raw_status": status_resp,
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_vision_job_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll the status of an existing Document Intelligence job. "
            "Returns the current job state and page metrics. Once state is "
            "'Completed', the output can be downloaded from the output URL."
        ),
    )
    async def sarvam_vision_job_status(
        ctx: Context,
        job_id: str = Field(description="The job_id returned by sarvam_tools_vision_extract."),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            status_resp, call = await sc.client.get_json(
                f"{DOC_JOB_BASE}/{job_id}/status"
            )
            metrics.merge(call)

        return {
            "job_id": job_id,
            "job_state": status_resp.get("job_state"),
            "page_metrics": status_resp.get("page_metrics"),
            "output_storage_path": status_resp.get("output_storage_path"),
            "raw": status_resp,
            "observability": metrics.to_response_block(),
        }


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
