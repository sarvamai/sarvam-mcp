"""Sarvam Vision — Document AI parse, schema extract, classify and split.

All jobs are asynchronous:

  POST /doc-ai/v1/job/parse | extract | classify | split
  GET  /doc-ai/v1/job/{job_id}/status
  GET  /doc-ai/v1/job/{job_id}/download-url   (parse)
  GET  /doc-ai/v1/job/{job_id}/results        (extract, classify, split)
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

DOC_AI_ROOT = "/doc-ai/v1"
DOC_AI_BASE = f"{DOC_AI_ROOT}/job"
PARSE_PATH = f"{DOC_AI_BASE}/parse"
EXTRACT_PATH = f"{DOC_AI_BASE}/extract"
CLASSIFY_PATH = f"{DOC_AI_BASE}/classify"
SPLIT_PATH = f"{DOC_AI_BASE}/split"

ParseFormat = Literal["md", "html", "json"]
ExtractFormat = Literal["json", "csv", "xlsx"]
ExtractMode = Literal["basic", "advanced"]
DocumentContent = Literal["printed", "handwritten", "mixed"]

TERMINAL = {"completed", "partially_completed", "failed", "rejected"}
MAX_POLL_ATTEMPTS = 60
POLL_INTERVAL_SECONDS = 5


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_vision_parse",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Parse a document with Sarvam Vision (POST /doc-ai/v1/job/parse). "
            "Full-document OCR that keeps layout, reading order, and tables. "
            "Output is markdown (`md`), HTML, or JSON.\n\n"
            "Uploads the file, polls until a terminal status, and returns the "
            "download URL. Limit: 20 pages per request (PDF or ZIP of JPG/PNG pages). "
            "Use `language` (not language_code). "
            "Pass `md`, not `markdown`."
        ),
    )
    async def sarvam_vision_parse(
        ctx: Context,
        document_path: str | None = Field(
            default=None,
            description="Local path to a PDF, PNG, JPEG, or ZIP. Up to 20 pages per request.",
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
        output_format: ParseFormat = Field(
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
                        PARSE_PATH,
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
            "For full-document OCR to markdown or HTML, use sarvam_tools_vision_parse.\n\n"
            "Limit: 500 pages per request (PDF or ZIP of JPG/PNG pages). `mode='advanced'` adds "
            "a second whole-document pass — slower and priced higher per page (₹2.50 vs ₹1.00)."
        ),
    )
    async def sarvam_vision_extract(
        ctx: Context,
        document_path: str | None = Field(
            default=None,
            description="Local path to a PDF, PNG, JPEG, or ZIP. Up to 500 pages per request.",
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
        mode: ExtractMode = Field(
            default="basic",
            description=(
                "'basic' (default) reads each field where it is printed. 'advanced' adds a "
                "second reading of the whole document: slower and more expensive per page."
            ),
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        if schema is None and not config_id:
            raise ValueError("Provide schema or config_id.")
        if schema is not None and config_id:
            raise ValueError("Provide exactly one of schema or config_id, not both.")
        form: dict[str, Any] = {
            "language": language,
            "output_format": output_format,
            "model": "sarvam-vision-v1",
            "mode": mode,
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
        name="sarvam_tools_vision_classify",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Classify a document with Sarvam Vision (POST /doc-ai/v1/job/classify). Returns ONE "
            "decision for the document (there is no per-page scope — for an answer per document "
            "in a bundle, use sarvam_tools_vision_split with categories). Labels it against the "
            "`categories` you define (each needs `type`; `description` optional but improves "
            "accuracy) and/or your `instructions`. Omit both to get a suggested document type.\n\n"
            "Choose pages with `max_pages` OR `page_ranges`, never both (422 PAGE_SELECTION_CONFLICT). "
            "With neither, the service reads the first 2 pages and the last, more only when unsure.\n\n"
            "Uploads the file, polls until a terminal status, and returns the result from "
            "GET /doc-ai/v1/job/{job_id}/results. A bundle of several documents comes back as "
            "classification_status='mixed' — split it first. Check `review_required` before trusting a "
            "label; `confidence` can be null.\n\n"
            "Limits: 20 pages per request, 10 documents per request, up to 200 categories, "
            "512 MB per document. PDF, PNG, JPEG or TIFF."
        ),
    )
    async def sarvam_vision_classify(
        ctx: Context,
        document_path: str | None = Field(
            default=None,
            description="Local path to a PDF, PNG, JPEG, or TIFF.",
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
        categories: list[dict[str, Any]] | None = Field(
            default=None,
            description=(
                "Up to 200 categories, e.g. [{'type': 'invoice', 'description': 'A supplier bill "
                "with totals', 'identifier_key': 'invoice number'}]. `type` is required (max 200 "
                "chars); `description` (max 2000) and `identifier_key` are optional; "
                "`positive_examples` / `negative_examples` (up to 8 each) are also accepted."
            ),
        ),
        instructions: str | None = Field(
            default=None, max_length=8000,
            description="Your own instruction text (max 8,000 chars). Can replace categories.",
        ),
        unmatched_behavior: Literal["suggest_type", "other"] | None = Field(
            default=None,
            description=(
                "When no category matches: 'suggest_type' returns a suggested_type "
                "(API default), 'other' returns type 'other'."
            ),
        ),
        min_class_confidence: float | None = Field(
            default=None, ge=0.0, le=1.0,
            description="Review threshold for a class match (API default 0.9).",
        ),
        max_pages: int | None = Field(
            default=None, ge=1, le=1000,
            description="Read the first N pages. Cannot be combined with page_ranges.",
        ),
        page_ranges: str | None = Field(
            default=None,
            description=(
                "1-based inclusive pages to read, e.g. '1-3,5,9-12'. "
                "Cannot be combined with max_pages."
            ),
        ),
        context: str | None = Field(
            default=None, max_length=4000, description="Background text for the model.",
        ),
        language: str | None = Field(
            default=None,
            description="BCP-47 document language, e.g. 'hi-IN'. Omit for the Indic OCR default.",
        ),
        include_details: bool = Field(
            default=False,
            description="Add inspected pages and provenance to the result (?include=details).",
        ),
        include_evidence: bool = Field(
            default=False, description="Ask the API to add supporting evidence to the result.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        if max_pages is not None and page_ranges:
            raise ValueError(
                "Send max_pages or page_ranges, not both "
                "(the API returns 422 PAGE_SELECTION_CONFLICT)."
            )
        config: dict[str, Any] = {}
        if categories:
            config["categories"] = categories
        if instructions:
            config["instructions"] = instructions
        if unmatched_behavior:
            config["unmatched_behavior"] = unmatched_behavior
        if min_class_confidence is not None:
            config["review_policy"] = {"min_class_confidence": min_class_confidence}
        if page_ranges:
            config["page_ranges"] = page_ranges
        request: dict[str, Any] = {"config": config}
        if max_pages is not None:
            request["max_pages"] = max_pages
        if context:
            request["context"] = context
        if language:
            request["language"] = language
        if include_evidence:
            request["output"] = {"include_evidence": True}
        return await _run_results_job(
            ctx,
            sc,
            CLASSIFY_PATH,
            request,
            document_path=document_path,
            document_base64=document_base64,
            document_url=document_url,
            filename=filename,
            include_details=include_details,
        )

    @mcp.tool(
        name="sarvam_tools_vision_split",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Split a bundle of pages into separate child documents with Sarvam Vision "
            "(POST /doc-ai/v1/job/split). The model always finds the boundaries — there is no "
            "`method`. Each segment keeps its original page numbers and a `document_ref`. Pass "
            "`categories` to also label each segment (set `classify_segments=False` to split only).\n\n"
            "Use `instructions` to guide the split, `page_ranges` to limit pages, and "
            "`must_keep_together` / `must_split_before` to force boundaries.\n\n"
            "Uploads the file, polls until a terminal status, and returns the result "
            "from GET /doc-ai/v1/job/{job_id}/results. `completed` means processing "
            "finished, not that every segment passed review — check each segment's "
            "review_required.\n\n"
            "Limits: 500 pages, 10 documents per request, up to 200 categories, 512 MB per "
            "document. PDF, PNG, JPEG or TIFF."
        ),
    )
    async def sarvam_vision_split(
        ctx: Context,
        document_path: str | None = Field(
            default=None,
            description="Local path to a PDF, PNG, JPEG, or TIFF.",
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
        categories: list[dict[str, Any]] | None = Field(
            default=None,
            description=(
                "Up to 200 categories to label each child document: {'type' (required), "
                "'description', 'identifier_key' (fills each document's `identifier`), "
                "'positive_examples', 'negative_examples'}. Omit to leave segments unlabelled."
            ),
        ),
        classify_segments: bool | None = Field(
            default=None,
            description=(
                "Classify each child document. Defaults to True when `categories` are given, "
                "otherwise False (split only). With False, categories must be omitted."
            ),
        ),
        instructions: str | None = Field(
            default=None, max_length=8000, description="Instructions for how to split (max 8,000 chars).",
        ),
        page_ranges: str | None = Field(
            default=None, description="Pages to split, 1-based inclusive, e.g. '1-3,5'. Default: every page.",
        ),
        must_keep_together: list[dict[str, int]] | None = Field(
            default=None,
            description="Page runs that must stay in one document, e.g. [{'start': 3, 'end': 4}].",
        ),
        must_split_before: list[int] | None = Field(
            default=None, description="Pages that always start a new document, e.g. [5, 9].",
        ),
        min_segment_confidence: float | None = Field(
            default=None, ge=0.0, le=1.0, description="Review threshold for a boundary (API default 0.9).",
        ),
        min_class_confidence: float | None = Field(
            default=None, ge=0.0, le=1.0, description="Review threshold for a class match (API default 0.9).",
        ),
        context: str | None = Field(
            default=None, description="Background text for the model.",
        ),
        language: str | None = Field(
            default=None, description="BCP-47 document language, e.g. 'hi-IN'.",
        ),
        include_details: bool = Field(
            default=False,
            description="Add inspected pages, provenance and boundary details to the result.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        classify = bool(categories) if classify_segments is None else classify_segments
        if categories and not classify:
            raise ValueError("categories need classify_segments=True (or omit classify_segments).")
        config: dict[str, Any] = {"classify_segments": classify}
        if categories:
            config["categories"] = categories
        if instructions:
            config["instructions"] = instructions
        if page_ranges:
            config["page_ranges"] = page_ranges
        constraints: dict[str, Any] = {}
        if must_keep_together:
            constraints["must_keep_together"] = must_keep_together
        if must_split_before:
            constraints["must_split_before"] = must_split_before
        if constraints:
            config["constraints"] = constraints
        review: dict[str, Any] = {}
        if min_segment_confidence is not None:
            review["min_segment_confidence"] = min_segment_confidence
        if min_class_confidence is not None:
            review["min_class_confidence"] = min_class_confidence
        if review:
            config["review_policy"] = review
        request: dict[str, Any] = {"config": config}
        if context:
            request["context"] = context
        if language:
            request["language"] = language
        return await _run_results_job(
            ctx,
            sc,
            SPLIT_PATH,
            request,
            document_path=document_path,
            document_base64=document_base64,
            document_url=document_url,
            filename=filename,
            include_details=include_details,
        )

    @mcp.tool(
        name="sarvam_tools_vision_capabilities",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "What Document AI offers on your deployment right now (GET /doc-ai/v1/capabilities): "
            "operations, input formats, split options, reasoning input modes, feature flags and the "
            "live limits (max_source_pages, max_source_bytes, max_categories, max_segments). Use it "
            "to confirm limits instead of relying on static text."
        ),
    )
    async def sarvam_vision_capabilities(ctx: Context) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            caps, call = await sc.client.get_json(f"{DOC_AI_ROOT}/capabilities")
            metrics.merge(call)
        body = caps if isinstance(caps, dict) else {}
        return {
            "api_contract": body.get("api_contract"),
            "operations": body.get("operations"),
            "input_formats": body.get("input_formats"),
            "reasoning_input_modes": body.get("reasoning_input_modes"),
            "split_methods": body.get("split_methods"),
            "features": body.get("features"),
            "limits": body.get("limits"),
            "retention_seconds": body.get("retention_seconds"),
            "raw": body,
            "observability": metrics.to_response_block(),
        }

    @mcp.tool(
        name="sarvam_tools_vision_job_status",
        description=(
            "Runtime tool — calls Sarvam API now.\n\n"
            "Poll a Document AI job at GET /doc-ai/v1/job/{job_id}/status. "
            "Works for parse, extract, classify and split jobs. Terminal statuses: "
            "completed, partially_completed, failed, rejected."
        ),
    )
    async def sarvam_vision_job_status(
        ctx: Context,
        job_id: str = Field(description="Job id from a vision parse, extract, classify or split call."),
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


async def _run_results_job(
    ctx: Context,
    sc: Any,
    path: str,
    request: dict[str, Any],
    *,
    document_path: str | None,
    document_base64: str | None,
    document_url: str | None,
    filename: str | None,
    include_details: bool,
) -> dict[str, Any]:
    """Submit a classify/split job (multipart `file` + JSON `request`), poll, fetch results."""
    async with resolve_file_input(
        file_path=document_path,
        file_base64=document_base64,
        file_url=document_url,
        filename=filename,
    ) as doc:
        with measure_tool() as metrics:
            with doc.open("rb") as fh:
                created, call = await sc.client.post_multipart(
                    path,
                    files={
                        "file": (doc.name, fh, _guess_doc_mime(doc)),
                        "request": (None, json.dumps(request), "application/json"),
                    },
                )
            metrics.merge(call)
            job_id = created["job_id"]
            status = await _poll_job(ctx, sc, job_id, metrics)
            results = None
            if str(status.get("status", "")).lower() in {"completed", "partially_completed"}:
                results, call = await sc.client.get_json(
                    f"{DOC_AI_BASE}/{job_id}/results",
                    params={"include": "details"} if include_details else None,
                )
                metrics.merge(call)

    body = results if isinstance(results, dict) else {}
    result = body.get("result")
    return {
        "job_id": job_id,
        "status": status.get("status"),
        "usage": status.get("usage"),
        "review_required": result.get("review_required") if isinstance(result, dict) else None,
        "result": result,
        "raw": results,
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
        "doc": "application/msword",
        "odt": "application/vnd.oasis.opendocument.text",
        "xls": "application/vnd.ms-excel",
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
        "ppt": "application/vnd.ms-powerpoint",
        "odp": "application/vnd.oasis.opendocument.presentation",
        "xhtml": "application/xhtml+xml",
        "mhtml": "multipart/related",
        "md": "text/markdown",
        "markdown": "text/markdown",
        "txt": "text/plain",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(suffix, "application/octet-stream")
