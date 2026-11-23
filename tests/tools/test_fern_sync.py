"""Mismatches found by comparing the MCP with sarvamai/sarvam-fern-config (docs source + PRs)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from sarvam_mcp.code.snippets import _validate
from sarvam_mcp.tools import dubbing, embeddings, llm, stt, transliterate, tts, vision
from tests.tools.conftest import call_tool

B64 = base64.b64encode(b"x").decode()


# ---- TTS: documented `language_code` + API defaults ------------------------


async def test_tts_sends_documented_language_code_and_api_defaults(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/text-to-speech", json={"audios": [B64], "request_id": "r"}
    )
    await call_tool(
        make_server(tts), "sarvam_tools_tts_speak", text="hi", target_language_code="hi-IN"
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["language_code"] == "hi-IN" and "target_language_code" not in body
    assert body["speech_sample_rate"] == 22050  # API default (was 24000)
    assert body["enable_preprocessing"] is False  # API default (was True)


def test_validator_accepts_documented_and_legacy_tts_language_field():
    base = {"text": "hi", "speaker": "shubh", "model": "bulbul:v3"}
    ok = _validate("/text-to-speech", {**base, "language_code": "hi-IN"})
    legacy = _validate("/text-to-speech", {**base, "target_language_code": "hi-IN"})
    missing = _validate("/text-to-speech", base)
    assert not [i for i in ok if "language" in str(i)]
    assert not [i for i in legacy if "Required" in str(i)]
    assert any("language_code" in str(i) for i in missing)


# ---- STT: realtime default + full codec enum -------------------------------


def test_realtime_default_is_saaras_v4():
    import inspect

    src = inspect.getsource(stt.register)
    assert 'default="saaras:v4"' in src.split("sarvam_stt_realtime")[1]


async def test_stt_accepts_documented_non_pcm_codec(make_server, httpx_mock):
    httpx_mock.add_response(url="https://api.sarvam.ai/speech-to-text", json={"transcript": "hi"})
    await call_tool(
        make_server(stt),
        "sarvam_tools_stt_transcribe",
        audio_base64=B64,
        filename="a.wav",
        input_audio_codec="x-m4a",
    )
    assert b"x-m4a" in httpx_mock.get_requests()[0].content


# ---- LLM: API defaults + reasoning rules (fern PR #781) --------------------


async def test_llm_omits_temperature_and_top_p_unless_set(make_server, httpx_mock):
    for _ in range(2):
        httpx_mock.add_response(
            url="https://api.sarvam.ai/v1/chat/completions",
            json={"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]},
        )
    await call_tool(
        make_server(llm), "sarvam_tools_llm_complete", messages=[{"role": "user", "content": "x"}]
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert "temperature" not in body and "top_p" not in body
    await call_tool(
        make_server(llm),
        "sarvam_tools_llm_complete",
        messages=[{"role": "user", "content": "x"}],
        temperature=0.3,
    )
    assert json.loads(httpx_mock.get_requests()[1].content)["temperature"] == 0.3


async def test_reasoning_none_sends_null_on_v1(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v1/chat/completions",
        json={"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]},
    )
    await call_tool(
        make_server(llm),
        "sarvam_tools_llm_complete",
        messages=[{"role": "user", "content": "x"}],
        reasoning_effort="none",
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert "reasoning_effort" in body and body["reasoning_effort"] is None


async def test_conversations_model_level_is_accepted_but_warned(make_server, httpx_mock):
    # Docs: sarvam-105b-conversations runs with reasoning off only; a level is accepted but ignored.
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v1/chat/completions",
        json={"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]},
    )
    out = await call_tool(
        make_server(llm),
        "sarvam_tools_llm_complete",
        model="sarvam-105b-conversations",
        messages=[{"role": "user", "content": "x"}],
        reasoning_effort="high",
    )
    assert "ignored" in out["warnings"][0]


# ---- Document AI: extract mode, limits text --------------------------------


async def test_extract_sends_mode_and_rejects_schema_plus_config(make_server, httpx_mock, tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    schema = {"type": "object", "properties": {"n": {"type": "string", "description": "name"}}}
    with pytest.raises(ToolError, match="exactly one"):
        await call_tool(
            make_server(vision),
            "sarvam_tools_vision_extract",
            document_path=str(pdf),
            schema=schema,
            config_id="c1",
        )
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/doc-ai/v1/job/extract",
        json={"job_id": "j", "status": "pending"},
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.sarvam.ai/doc-ai/v1/job/j/status",
        json={"status": "completed"},
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.sarvam.ai/doc-ai/v1/job/j/results",
        json={"result": {"n": "x"}},
    )
    await call_tool(
        make_server(vision),
        "sarvam_tools_vision_extract",
        document_path=str(pdf),
        schema=schema,
        mode="advanced",
    )
    assert b'name="mode"' in httpx_mock.get_requests()[0].content
    assert b"advanced" in httpx_mock.get_requests()[0].content


async def test_doc_ai_limit_text_matches_docs_table():
    from fastmcp import Client

    from sarvam_mcp.server import build_server

    async with Client(build_server()) as c:
        tools = {t.name: t.description for t in await c.list_tools()}
    assert "20 pages per request" in tools["sarvam_tools_vision_parse"]
    assert "500 pages per request" in tools["sarvam_tools_vision_extract"]
    assert "20 pages per request" in tools["sarvam_tools_vision_classify"]
    assert "500 pages" in tools["sarvam_tools_vision_split"]
    assert "30 pages" not in tools["sarvam_tools_vision_parse"]


# ---- Dubbing export options ------------------------------------------------


async def test_dubbing_documented_export_options(make_server, httpx_mock, tmp_path):
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/dubbing/jobs",
        json={"data": {"job_id": "d", "upload_url": "https://blob.test/v?s=1"}},
    )
    httpx_mock.add_response(method="PUT", url="https://blob.test/v?s=1", status_code=201)
    httpx_mock.add_response(
        method="POST", url="https://api.sarvam.ai/dubbing/jobs/d/start", json={}
    )
    await call_tool(
        make_server(dubbing),
        "sarvam_tools_dubbing_submit",
        media_path=str(media),
        src_lang="en-IN",
        target_langs=["hi-IN"],
        export_options=["video", "audio_vocals", "vtt"],
    )
    assert json.loads(httpx_mock.get_requests()[0].content)["export_options"] == [
        "video",
        "audio_vocals",
        "vtt",
    ]


# ---- Transliterate language support ----------------------------------------


async def test_transliterate_rejects_unsupported_language(make_server, httpx_mock):
    with pytest.raises(ToolError, match="does not support"):
        await call_tool(
            make_server(transliterate),
            "sarvam_tools_transliterate",
            input="x",
            source_language_code="ur-IN",
            target_language_code="en-IN",
        )
    assert httpx_mock.get_requests() == []


# ---- Embeddings ------------------------------------------------------------


async def test_embed_prefixes_task_and_writes_file(make_server, httpx_mock, tmp_path):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/embeddings",
        json={
            "object": "list",
            "model": "embeddinggemma-2",
            "data": [
                {"object": "embedding", "index": 1, "embedding": [0.3] * 768},
                {"object": "embedding", "index": 0, "embedding": [0.1] * 768},
            ],
            "usage": {"prompt_tokens": 9, "total_tokens": 9, "completion_tokens": 0},
        },
    )
    out = await call_tool(
        make_server(embeddings), "sarvam_tools_embed", input=["a", "b"], task="query"
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body == {
        "model": "embeddinggemma-2",
        "encoding_format": "float",
        "input": ["task: search result | query: a", "task: search result | query: b"],
    }
    assert out["count"] == 2 and out["dimensions"] == 768 and "embeddings" not in out
    saved = json.loads(Path(out["file_path"]).read_text())
    assert saved["embeddings"][0][0] == 0.1  # re-ordered by `index`


async def test_embed_return_vectors_inline_and_validation(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/embeddings",
        json={
            "model": "embeddinggemma-2",
            "data": [{"index": 0, "embedding": [1.0, 0.0]}],
            "usage": {},
        },
    )
    out = await call_tool(
        make_server(embeddings), "sarvam_tools_embed", input="hello", return_vectors=True
    )
    assert out["embeddings"] == [[1.0, 0.0]]
    with pytest.raises(ToolError, match="at least one"):
        await call_tool(make_server(embeddings), "sarvam_tools_embed", input=[])
    with pytest.raises(ToolError):
        await call_tool(
            make_server(embeddings), "sarvam_tools_embed", input="x", encoding_format="int8"
        )
