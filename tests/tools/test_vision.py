"""Document AI tools — parse, classify, split — against a mocked Sarvam API.

Each test calls the tool through an in-memory MCP client, so argument
validation, the tool body, and the response shape are all the real thing;
only the HTTP layer is faked. Assertions focus on the wire format, since
that is what the live API is strict about.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.tools import vision

BASE = "https://api.sarvam.ai"
JOB = "job_abc123"


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch):
    monkeypatch.setattr(vision, "POLL_INTERVAL_SECONDS", 0)


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    path = tmp_path / "bundle.pdf"
    path.write_bytes(b"%PDF-1.4\n%fake\n")
    return path


@pytest.fixture
async def mcp(tmp_path: Path) -> AsyncIterator[FastMCP]:
    @asynccontextmanager
    async def lifespan(_server: FastMCP):
        client = SarvamClient(BASE)
        config = Config(base_path=tmp_path)
        try:
            yield ServerContext(
                config=config, client=client, audio_sink=build_sink("files", tmp_path)
            )
        finally:
            await client.aclose()

    server = FastMCP("test", lifespan=lifespan)
    vision.register(server)
    yield server


async def call(mcp: FastMCP, tool: str, **args: Any) -> dict[str, Any]:
    async with Client(mcp) as client:
        result = await client.call_tool(tool, args)
    return result.data


def multipart_parts(request: httpx.Request) -> dict[str, dict[str, Any]]:
    """Parse a multipart body into {field: {"filename", "content_type", "body"}}."""
    boundary = re.search(r'boundary=([^;]+)', request.headers["content-type"]).group(1)
    parts: dict[str, dict[str, Any]] = {}
    for chunk in request.content.split(f"--{boundary}".encode())[1:-1]:
        head, _, body = chunk.lstrip(b"\r\n").partition(b"\r\n\r\n")
        head_text = head.decode()
        name = re.search(r'name="([^"]+)"', head_text).group(1)
        filename = re.search(r'filename="([^"]*)"', head_text)
        ctype = re.search(r"(?im)^content-type:\s*(\S+)", head_text)
        parts[name] = {
            "filename": filename.group(1) if filename else None,
            "content_type": ctype.group(1) if ctype else None,
            "body": body.removesuffix(b"\r\n"),
        }
    return parts


def mock_job(httpx_mock, submit_path: str, *, results: dict | None = None,
             statuses: tuple[str, ...] = ("completed",)) -> None:
    httpx_mock.add_response(
        method="POST", url=f"{BASE}{submit_path}", json={"job_id": JOB, "status": "pending"},
        headers={"x-request-id": "req_submit"},
    )
    for state in statuses:
        httpx_mock.add_response(
            method="GET", url=f"{BASE}/doc-ai/v1/job/{JOB}/status",
            json={"job_id": JOB, "status": state, "usage": {"pages_processed": 3}},
        )
    if results is not None:
        httpx_mock.add_response(
            method="GET", url=re.compile(rf"{BASE}/doc-ai/v1/job/{JOB}/results.*"), json=results
        )


# ---- classify -------------------------------------------------------------


CATEGORIES = [
    {"type": "invoice", "description": "A supplier bill with totals"},
    {"type": "receipt", "description": "A proof of payment"},
]


async def test_classify_sends_file_and_json_request_part(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", results={
        "result": {"classification_status": "classified", "review_required": False,
                   "type": "invoice", "confidence": 0.93},
    })

    out = await call(
        mcp, "sarvam_tools_vision_classify",
        document_path=str(pdf), categories=CATEGORIES, language="hi-IN", max_pages=2,
        unmatched_behavior="other",
    )

    submit = next(r for r in httpx_mock.get_requests() if r.method == "POST")
    assert submit.headers["api-subscription-key"] == "sk_test_key_for_unit_tests_abcd"
    parts = multipart_parts(submit)
    assert set(parts) == {"file", "request"}
    assert parts["file"]["filename"] == "bundle.pdf"
    assert parts["file"]["content_type"] == "application/pdf"
    assert parts["request"]["content_type"] == "application/json"
    assert parts["request"]["filename"] is None  # plain form field, not a file upload
    assert json.loads(parts["request"]["body"]) == {
        "language": "hi-IN",
        "config": {
            "scope": "document", "categories": CATEGORIES,
            "unmatched_behavior": "other", "max_pages": 2,
        },
    }
    assert out["job_id"] == JOB
    assert out["status"] == "completed"
    assert out["review_required"] is False
    assert out["result"]["type"] == "invoice"
    assert out["usage"] == {"pages_processed": 3}


async def test_classify_minimal_request_omits_unset_fields(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", results={"result": {"review_required": True}})

    out = await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))

    request = json.loads(multipart_parts(httpx_mock.get_requests()[0])["request"]["body"])
    assert request == {"config": {"scope": "document"}}
    assert out["review_required"] is True


async def test_classify_page_scope_and_details_flag(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", results={"result": {"pages": []}})

    await call(mcp, "sarvam_tools_vision_classify",
               document_path=str(pdf), scope="page", include_details=True)

    requests = httpx_mock.get_requests()
    request = json.loads(multipart_parts(requests[0])["request"]["body"])
    assert request["config"]["scope"] == "page"
    results_req = requests[-1]
    assert results_req.url.path == f"/doc-ai/v1/job/{JOB}/results"
    assert results_req.url.params["include"] == "details"


async def test_results_request_has_no_include_param_by_default(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", results={"result": {}})

    await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))

    assert "include" not in httpx_mock.get_requests()[-1].url.params


async def test_classify_polls_until_terminal(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify",
             statuses=("pending", "running", "completed"),
             results={"result": {"type": "invoice"}})

    out = await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))

    status_calls = [r for r in httpx_mock.get_requests() if r.url.path.endswith("/status")]
    assert len(status_calls) == 3
    assert out["result"] == {"type": "invoice"}


@pytest.mark.parametrize("terminal", ["failed", "rejected"])
async def test_classify_failed_job_skips_results(mcp, pdf, httpx_mock, terminal):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", statuses=(terminal,))

    out = await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))

    assert out["status"] == terminal
    assert out["result"] is None and out["raw"] is None and out["review_required"] is None
    assert not [r for r in httpx_mock.get_requests() if r.url.path.endswith("/results")]


async def test_partially_completed_still_fetches_results(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", statuses=("partially_completed",),
             results={"result": {"review_required": True}})

    out = await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))

    assert out["status"] == "partially_completed"
    assert out["review_required"] is True


async def test_classify_poll_timeout_points_to_job_status(mcp, pdf, httpx_mock, monkeypatch):
    monkeypatch.setattr(vision, "MAX_POLL_ATTEMPTS", 2)
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", statuses=("running", "running"))

    with pytest.raises(ToolError, match="sarvam_tools_vision_job_status"):
        await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))


async def test_classify_accepts_base64_input(mcp, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", results={"result": {}})
    payload = base64.b64encode(b"\x89PNG fake").decode()

    await call(mcp, "sarvam_tools_vision_classify", document_base64=payload, filename="scan.png")

    file_part = multipart_parts(httpx_mock.get_requests()[0])["file"]
    assert file_part["content_type"] == "image/png"
    assert file_part["body"] == b"\x89PNG fake"


async def test_classify_requires_exactly_one_input(mcp):
    with pytest.raises(ToolError, match="exactly one"):
        await call(mcp, "sarvam_tools_vision_classify")


async def test_classify_rejects_bad_scope(mcp, pdf):
    with pytest.raises(ToolError):
        await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf), scope="paragraph")


async def test_classify_api_400_surfaces_message(mcp, pdf, httpx_mock):
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/doc-ai/v1/job/classify", status_code=400,
        json={"error": {"message": "categories must have unique names", "code": "invalid_request"}},
    )

    with pytest.raises(ToolError, match="unique names"):
        await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf), categories=CATEGORIES)


async def test_classify_auth_error_maps_to_tool_error(mcp, pdf, httpx_mock):
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/doc-ai/v1/job/classify", status_code=403,
        json={"error": {"message": "Invalid API key"}},
    )

    with pytest.raises(ToolError, match="Invalid API key"):
        await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))


# ---- split ----------------------------------------------------------------


async def test_split_semantic_default(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/split", results={
        "result": {"review_required": False, "segments": [
            {"document_ref": "doc_1", "pages": [1, 2]}, {"document_ref": "doc_2", "pages": [3]},
        ]},
    })

    out = await call(mcp, "sarvam_tools_vision_split", document_path=str(pdf))

    parts = multipart_parts(httpx_mock.get_requests()[0])
    assert set(parts) == {"file", "request"}
    assert json.loads(parts["request"]["body"]) == {
        "config": {"method": "semantic", "classify_segments": False}
    }
    assert [s["document_ref"] for s in out["result"]["segments"]] == ["doc_1", "doc_2"]
    assert out["review_required"] is False


async def test_split_fixed_pages(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/split", results={"result": {}})

    await call(mcp, "sarvam_tools_vision_split",
               document_path=str(pdf), method="fixed_pages", pages_per_segment=2)

    config = json.loads(multipart_parts(httpx_mock.get_requests()[0])["request"]["body"])["config"]
    assert config == {"method": "fixed_pages", "classify_segments": False, "pages_per_segment": 2}


async def test_split_page_ranges(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/split", results={"result": {}})
    ranges = [{"start": 1, "end": 2}, {"start": 3, "end": 4}]

    await call(mcp, "sarvam_tools_vision_split",
               document_path=str(pdf), method="page_ranges", segment_ranges=ranges)

    config = json.loads(multipart_parts(httpx_mock.get_requests()[0])["request"]["body"])["config"]
    assert config["method"] == "page_ranges" and config["segment_ranges"] == ranges


async def test_split_triggers(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/split", results={"result": {}})
    split_on = [{"type": "text", "match": {"prefix": "INVOICE"}}]

    await call(mcp, "sarvam_tools_vision_split",
               document_path=str(pdf), method="triggers", split_on=split_on)

    config = json.loads(multipart_parts(httpx_mock.get_requests()[0])["request"]["body"])["config"]
    assert config["method"] == "triggers" and config["split_on"] == split_on


async def test_split_with_categories_turns_on_classify_segments(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/split", results={"result": {}})

    await call(mcp, "sarvam_tools_vision_split",
               document_path=str(pdf), categories=CATEGORIES, language="en-IN")

    request = json.loads(multipart_parts(httpx_mock.get_requests()[0])["request"]["body"])
    assert request["language"] == "en-IN"
    assert request["config"]["classify_segments"] is True
    assert request["config"]["categories"] == CATEGORIES


@pytest.mark.parametrize(
    ("method", "needs"),
    [("fixed_pages", "pages_per_segment"), ("page_ranges", "segment_ranges"),
     ("triggers", "split_on")],
)
async def test_split_method_requires_its_argument(mcp, pdf, method, needs):
    with pytest.raises(ToolError, match=needs):
        await call(mcp, "sarvam_tools_vision_split", document_path=str(pdf), method=method)


async def test_split_rejects_unknown_method(mcp, pdf):
    with pytest.raises(ToolError):
        await call(mcp, "sarvam_tools_vision_split", document_path=str(pdf), method="magic")


async def test_split_include_details(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/split", results={"result": {}})

    await call(mcp, "sarvam_tools_vision_split", document_path=str(pdf), include_details=True)

    assert httpx_mock.get_requests()[-1].url.params["include"] == "details"


# ---- parse (renamed from digitise) ---------------------------------------


async def test_parse_hits_parse_endpoint_with_form_fields(mcp, pdf, httpx_mock):
    httpx_mock.add_response(method="POST", url=f"{BASE}/doc-ai/v1/job/parse",
                            json={"job_id": JOB})
    httpx_mock.add_response(method="GET", url=f"{BASE}/doc-ai/v1/job/{JOB}/status",
                            json={"status": "completed"})
    httpx_mock.add_response(method="GET", url=f"{BASE}/doc-ai/v1/job/{JOB}/download-url",
                            json={"download_url": "https://blob/out.zip"})

    out = await call(mcp, "sarvam_tools_vision_parse", document_path=str(pdf),
                     output_format="html", language="hi-IN", document_content="mixed")

    parts = multipart_parts(httpx_mock.get_requests()[0])
    assert parts["file"]["filename"] == "bundle.pdf"
    assert parts["language"]["body"] == b"hi-IN"
    assert parts["output_format"]["body"] == b"html"
    assert parts["content_type"]["body"] == b"mixed"
    assert parts["model"]["body"] == b"sarvam-vision-v1"
    assert out["download"] == {"download_url": "https://blob/out.zip"}
    assert out["output_format"] == "html"


async def test_parse_rejects_markdown_alias(mcp, pdf):
    with pytest.raises(ToolError):
        await call(mcp, "sarvam_tools_vision_parse", document_path=str(pdf), output_format="markdown")


async def test_digitise_tool_is_gone(mcp):
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert "sarvam_tools_vision_digitise" not in names
    assert {"sarvam_tools_vision_parse", "sarvam_tools_vision_classify",
            "sarvam_tools_vision_split"} <= names


# ---- job status -----------------------------------------------------------


async def test_job_status_passthrough(mcp, httpx_mock):
    httpx_mock.add_response(method="GET", url=f"{BASE}/doc-ai/v1/job/{JOB}/status",
                            json={"status": "running", "usage": None})

    out = await call(mcp, "sarvam_tools_vision_job_status", job_id=JOB)

    assert out["job_id"] == JOB and out["status"] == "running"


# ---- observability + code-help routing -----------------------------------


async def test_response_carries_observability_block(mcp, pdf, httpx_mock):
    mock_job(httpx_mock, "/doc-ai/v1/job/classify", results={"result": {}})

    out = await call(mcp, "sarvam_tools_vision_classify", document_path=str(pdf))

    assert isinstance(out["observability"], dict) and out["observability"]


@pytest.mark.parametrize(
    ("task", "endpoint"),
    [
        ("classify this pdf document by type", "/doc-ai/v1/job/classify"),
        ("categorize my scanned invoice pages", "/doc-ai/v1/job/classify"),
        ("split a scanned bundle of pages into separate documents", "/doc-ai/v1/job/split"),
        ("ocr this pdf to markdown", "/doc-ai/v1/job/parse"),
    ],
)
def test_code_recommendation_routes_to_doc_ai_endpoint(task, endpoint):
    from sarvam_mcp.code.snippets import _recommend

    assert _recommend(task)["endpoint"] == endpoint


def test_no_stale_digitise_references_in_source():
    root = Path(__file__).resolve().parents[2]
    offenders = [
        str(p.relative_to(root))
        for p in [*(root / "src").rglob("*.py"), root / "README.md"]
        if "digitise" in p.read_text().lower()
    ]
    assert not offenders, f"stale 'digitise' references: {offenders}"
