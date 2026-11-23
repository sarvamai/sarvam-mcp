"""document_translate / dubbing request-body changes from the docs sync."""

from __future__ import annotations

import json

import pytest
from fastmcp.exceptions import ToolError

from sarvam_mcp.tools import document_translate, dubbing
from tests.tools.conftest import call_tool


async def _doc_translate(make_server, httpx_mock, tmp_path, **kw):
    doc = tmp_path / "a.pdf"
    doc.write_bytes(b"%PDF-1.4")
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/translate/document/jobs",
        json={"job_id": "j1", "upload_url": "https://blob.test/u?sig=1"},
    )
    httpx_mock.add_response(method="PUT", url="https://blob.test/u?sig=1", status_code=201)
    httpx_mock.add_response(
        method="POST", url="https://api.sarvam.ai/translate/document/jobs/j1/start", json={}
    )
    await call_tool(
        make_server(document_translate),
        "sarvam_tools_document_translate",
        document_path=str(doc),
        source_language_code="en-IN",
        **kw,
    )
    return json.loads(httpx_mock.get_requests()[0].content)


async def test_numerals_default_is_omitted_and_odia_normalised(make_server, httpx_mock, tmp_path):
    body = await _doc_translate(
        make_server, httpx_mock, tmp_path, target_language_codes=["od-IN", "hi-IN"]
    )
    assert "use_native_numerals" not in body  # null -> API default
    assert body["target_language_codes"] == ["or-IN", "hi-IN"]


async def test_numerals_and_language_guidelines_sent(make_server, httpx_mock, tmp_path):
    body = await _doc_translate(
        make_server,
        httpx_mock,
        tmp_path,
        target_language_codes=["hi-IN"],
        use_native_numerals=False,
        language_specific_guidelines={"hi-IN": "formal"},
    )
    assert body["use_native_numerals"] is False
    assert body["language_specific_guidelines"] == {"hi-IN": "formal"}


async def test_guidelines_keys_must_match_targets(make_server, httpx_mock, tmp_path):
    doc = tmp_path / "a.pdf"
    doc.write_bytes(b"x")
    with pytest.raises(ToolError, match="not in target_language_codes"):
        await call_tool(
            make_server(document_translate),
            "sarvam_tools_document_translate",
            document_path=str(doc),
            source_language_code="en-IN",
            target_language_codes=["hi-IN"],
            language_specific_guidelines={"ta-IN": "x"},
        )
    assert httpx_mock.get_requests() == []


async def test_dubbing_editor_flow_and_odia(make_server, httpx_mock, tmp_path):
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/dubbing/jobs",
        json={"data": {"job_id": "d1", "upload_url": "https://blob.test/v?sig=1"}},
    )
    httpx_mock.add_response(method="PUT", url="https://blob.test/v?sig=1", status_code=201)
    httpx_mock.add_response(
        method="POST", url="https://api.sarvam.ai/dubbing/jobs/d1/start", json={}
    )
    await call_tool(
        make_server(dubbing),
        "sarvam_tools_dubbing_submit",
        media_path=str(media),
        src_lang="en-IN",
        target_langs=["od-IN"],
        editor_flow=True,
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["editor_flow"] is True and body["target_langs"] == ["or-IN"]
