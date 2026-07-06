"""Vision tool: auto-detect language tokens fall back to the default language.

The shared ``LanguageCode`` enum exposes two auto-detect spellings — ``"auto"``
(Translate/Transliterate) and ``"unknown"`` (STT) — but the doc-digitization
API expects a concrete BCP-47 language. The tool mapped ``"unknown"`` to the
default language; ``"auto"`` leaked through unchanged and was sent as the job
language.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio.sinks import FileSink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.server import build_server

BASE_URL = "https://api.sarvam.ai"
JOB_BASE = f"{BASE_URL}/doc-digitization/job/v1"


def _make_ctx(tmp_path):
    server_ctx = ServerContext(
        config=Config(),
        client=SarvamClient(BASE_URL),
        audio_sink=FileSink(tmp_path),
    )

    async def _noop(*_args, **_kwargs):
        return None

    return SimpleNamespace(
        info=_noop,
        report_progress=_noop,
        request_context=SimpleNamespace(lifespan_context=server_ctx),
    )


@pytest.mark.parametrize("auto_token", ["auto", "unknown"])
async def test_vision_maps_auto_detect_tokens_to_default_language(
    auto_token, tmp_path, httpx_mock
):
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-1.4 test")

    httpx_mock.add_response(method="POST", url=JOB_BASE, json={"job_id": "job_123"})
    httpx_mock.add_response(
        method="POST",
        url=f"{JOB_BASE}/upload-files",
        json={"upload_urls": {"doc.pdf": {"file_url": "https://blob.example/up", "file_metadata": {}}}},
    )
    httpx_mock.add_response(method="PUT", url="https://blob.example/up", status_code=201)
    httpx_mock.add_response(method="POST", url=f"{JOB_BASE}/job_123/start", json={})
    httpx_mock.add_response(
        method="GET", url=f"{JOB_BASE}/job_123/status", json={"job_state": "Completed"}
    )

    tool = await build_server().get_tool("sarvam_tools_vision_extract")
    await tool.fn(
        ctx=_make_ctx(tmp_path),
        document_path=str(doc),
        document_base64=None,
        document_url=None,
        filename=None,
        output_format="md",
        language_code=auto_token,
    )

    create_req = httpx_mock.get_request(method="POST", url=JOB_BASE)
    body = json.loads(create_req.content)
    assert body["job_parameters"]["language"] == "hi-IN"
