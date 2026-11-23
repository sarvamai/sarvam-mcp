"""Tools added in the 2026-11 docs sync: Chat V2, Responses, models, Dictate,
Instant Voice Cloning, pronunciation update, TTS codec, 402 mapping."""

from __future__ import annotations

import base64
import json

import pytest
from fastmcp.exceptions import ToolError

from sarvam_mcp.tools import (
    dictate,
    llm,
    models,
    pronunciation,
    responses,
    transliterate,
    tts,
    voice_cloning,
)
from tests.tools.conftest import call_tool

AUDIO = base64.b64encode(b"RIFF....WAVEfmt fake audio bytes").decode()


# ---- LLM routing ----------------------------------------------------------


async def test_sarvam_models_stay_on_v1(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v1/chat/completions",
        json={"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]},
    )
    out = await call_tool(
        make_server(llm), "sarvam_tools_llm_complete", messages=[{"role": "user", "content": "x"}]
    )
    assert out["content"] == "hi"


async def test_open_weight_models_route_to_v2(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/chat/completions",
        json={"choices": [{"message": {"content": "yo"}, "finish_reason": "stop"}]},
    )
    out = await call_tool(
        make_server(llm),
        "sarvam_tools_llm_complete",
        model="glm5.3-flash",
        messages=[{"role": "user", "content": "x"}],
        reasoning_effort="high",
        top_k=20,
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert out["content"] == "yo"
    assert (
        body["model"] == "glm5.3-flash"
        and body["top_k"] == 20
        and body["reasoning_effort"] == "high"
    )


async def test_n_greater_than_one_rejected_before_call(make_server, httpx_mock):
    with pytest.raises(ToolError):
        await call_tool(
            make_server(llm),
            "sarvam_tools_llm_complete",
            messages=[{"role": "user", "content": "x"}],
            n=2,
        )
    assert httpx_mock.get_requests() == []


async def test_v2_only_params_rejected_on_v1_model(make_server, httpx_mock):
    with pytest.raises(ToolError, match="only supported on V2"):
        await call_tool(
            make_server(llm),
            "sarvam_tools_llm_complete",
            messages=[{"role": "user", "content": "x"}],
            top_k=5,
        )
    assert httpx_mock.get_requests() == []


async def test_provisioned_model_404_gets_access_hint(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/chat/completions",
        status_code=404,
        json={"error": {"message": "model not found"}},
    )
    with pytest.raises(ToolError, match="Provisioned Throughput"):
        await call_tool(
            make_server(llm),
            "sarvam_tools_llm_complete",
            model="qwen38-27b",
            messages=[{"role": "user", "content": "x"}],
        )


async def test_402_maps_to_quota_error(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v1/chat/completions",
        status_code=402,
        json={"error": {"message": "no credits", "code": "insufficient_quota_error"}},
    )
    with pytest.raises(ToolError, match="credits are exhausted"):
        await call_tool(
            make_server(llm),
            "sarvam_tools_llm_complete",
            messages=[{"role": "user", "content": "x"}],
        )


# ---- Responses / models ---------------------------------------------------


async def test_responses_flat_tools_enforced(make_server, httpx_mock):
    with pytest.raises(ToolError, match="flat shape"):
        await call_tool(
            make_server(responses),
            "sarvam_tools_responses_create",
            input="hi",
            tools=[{"type": "function", "function": {"name": "f"}}],
        )
    assert httpx_mock.get_requests() == []


async def test_responses_extracts_output_text(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/responses",
        json={
            "status": "completed",
            "model": "sarvam-105b",
            "output": [
                {"type": "reasoning"},
                {"type": "message", "content": [{"type": "output_text", "text": "namaste"}]},
            ],
        },
    )
    out = await call_tool(
        make_server(responses),
        "sarvam_tools_responses_create",
        input="hi",
        max_output_tokens=50,
        reasoning_effort="low",
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert out["output_text"] == "namaste"
    assert body["reasoning"] == {"effort": "low"} and body["max_output_tokens"] == 50
    assert "store" not in body


async def test_list_models(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/models",
        json={
            "object": "list",
            "data": [{"id": "glm5.3", "created": 0, "owned_by": "sarvam", "access": "standard"}],
        },
    )
    out = await call_tool(make_server(models), "sarvam_tools_list_models")
    assert out["count"] == 1 and out["models"][0]["id"] == "glm5.3"


# ---- Dictate --------------------------------------------------------------


async def test_dictate_clip_sends_json_form_parts_only_when_set(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/dictate",
        json={
            "request_id": "r1",
            "text": "Hello Aditya.",
            "transcript": "hello aditya",
            "language_code": "en-IN",
            "corrections": [],
            "degraded": None,
            "usage": {"audio_duration_s": 2.0, "words": 2},
        },
    )
    out = await call_tool(
        make_server(dictate),
        "sarvam_tools_dictate_clip",
        audio_base64=AUDIO,
        filename="c.wav",
        style_preset="clean",
        vocabulary=[{"word": "Aditya", "sounds_like": ["adithya"]}],
    )
    req = httpx_mock.get_requests()[0]
    raw = req.content.decode(errors="ignore")
    assert out["text"] == "Hello Aditya."
    assert 'name="style"' in raw and '{"preset": "clean"}' in raw
    assert 'name="vocabulary"' in raw
    assert 'name="mode"' not in raw and 'name="context"' not in raw  # empty parts would 400


async def test_dictate_clip_rejects_bad_vocabulary(make_server, httpx_mock):
    with pytest.raises(ToolError, match="non-empty 'word'"):
        await call_tool(
            make_server(dictate),
            "sarvam_tools_dictate_clip",
            audio_base64=AUDIO,
            filename="c.wav",
            vocabulary=[{"sounds_like": ["x"]}],
        )
    assert httpx_mock.get_requests() == []


async def test_dictate_job_url_is_multipart_without_file(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/dictate/jobs",
        status_code=202,
        json={"job_id": "j1", "job_state": "Accepted"},
    )
    out = await call_tool(
        make_server(dictate),
        "sarvam_tools_dictate_job_submit",
        audio_url="https://example.com/a.mp3",
    )
    req = httpx_mock.get_requests()[0]
    assert req.headers["content-type"].startswith("multipart/form-data")
    assert b'name="audio_url"' in req.content
    assert out["job_id"] == "j1"


async def test_dictate_job_requires_exactly_one_source(make_server, httpx_mock):
    with pytest.raises(ToolError, match="exactly one"):
        await call_tool(make_server(dictate), "sarvam_tools_dictate_job_submit")
    with pytest.raises(ToolError, match="exactly one"):
        await call_tool(
            make_server(dictate),
            "sarvam_tools_dictate_job_submit",
            audio_url="https://x.test/a.mp3",
            audio_base64=AUDIO,
            filename="a.wav",
        )


async def test_dictate_job_status(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/v2/dictate/jobs/j1",
        json={
            "job_id": "j1",
            "job_state": "Completed",
            "result": {"text": "done", "model": "dictate-v1"},
        },
    )
    out = await call_tool(make_server(dictate), "sarvam_tools_dictate_job_status", job_id="j1")
    assert out["text"] == "done" and out["job_state"] == "Completed"


# ---- Voice cloning --------------------------------------------------------


async def test_voice_create_returns_voice_id(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/voices/create",
        status_code=201,
        json={
            "status": "success",
            "data": {
                "voice_id": "svc-1",
                "status": "saved",
                "reference_text": "hi",
                "background_noise_removed": True,
            },
        },
    )
    out = await call_tool(
        make_server(voice_cloning),
        "sarvam_tools_cloned_voice_create",
        name="Me",
        language="hi-IN",
        audio_base64=AUDIO,
        filename="ref.wav",
    )
    assert out["voice_id"] == "svc-1"


async def test_voice_speak_needs_exactly_one_voice_source(make_server, httpx_mock):
    with pytest.raises(ToolError, match="exactly one of voice_id"):
        await call_tool(make_server(voice_cloning), "sarvam_tools_cloned_voice_speak", text="hi")
    with pytest.raises(ToolError, match="mutually exclusive"):
        await call_tool(
            make_server(voice_cloning),
            "sarvam_tools_cloned_voice_speak",
            text="hi",
            voice_id="svc-1",
            pace=1.0,
            max_audio_duration=3.0,
        )
    assert httpx_mock.get_requests() == []


async def test_voice_speak_writes_audio_in_requested_codec(make_server, httpx_mock, tmp_path):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/voices/clone",
        json={
            "audio_b64": base64.b64encode(b"mp3bytes").decode(),
            "request_id": "r",
            "audio_duration": 1.2,
        },
    )
    out = await call_tool(
        make_server(voice_cloning),
        "sarvam_tools_cloned_voice_speak",
        text="hello",
        voice_id="svc-1",
        output_audio_codec="mp3",
    )
    req = httpx_mock.get_requests()[0]
    assert req.headers["content-type"].startswith("multipart/form-data")
    assert b'name="voice_id"' in req.content and b"svc-1" in req.content
    assert out["file_path"].endswith(".mp3") and out["mime_type"] == "audio/mpeg"


async def test_voice_delete_and_list_paths(make_server, httpx_mock):
    httpx_mock.add_response(
        method="DELETE", url="https://api.sarvam.ai/voices/delete/svc-1", status_code=204
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.sarvam.ai/voices?limit=50&offset=0",
        json={"status": "success", "data": {"voices": [{"id": "svc-1"}], "total": 1}},
    )
    server = make_server(voice_cloning)
    assert (await call_tool(server, "sarvam_tools_cloned_voice_delete", voice_id="svc-1"))[
        "deleted"
    ] is True
    assert (await call_tool(server, "sarvam_tools_cloned_voice_list"))["total"] == 1


async def test_watermark_detect(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/voices/watermark/detect",
        json={
            "status": "success",
            "data": {
                "verdict": "watermarked",
                "z_score": 5.1,
                "analysed_seconds": 8.0,
                "inconclusive": False,
            },
        },
    )
    out = await call_tool(
        make_server(voice_cloning),
        "sarvam_tools_cloned_voice_watermark_detect",
        audio_base64=AUDIO,
        filename="a.wav",
    )
    assert out["verdict"] == "watermarked"


# ---- Pronunciation update / TTS / transliterate ---------------------------


async def test_pronunciation_update_uses_put_with_dict_id(make_server, httpx_mock):
    httpx_mock.add_response(
        method="PUT",
        url="https://api.sarvam.ai/text-to-speech/pronunciation-dictionary?dict_id=p_abc12345",
        json={
            "dictionary_id": "p_abc12345",
            "updated_pronunciations": {"hi-IN": {"CEO": "see ee oh"}},
        },
    )
    out = await call_tool(
        make_server(pronunciation),
        "sarvam_tools_pronunciation_update",
        dictionary_id="p_abc12345",
        entries={"CEO": "see ee oh"},
    )
    assert out["updated_pronunciations"] == {"hi-IN": {"CEO": "see ee oh"}}


async def test_tts_codec_and_temperature(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/text-to-speech",
        json={"audios": [base64.b64encode(b"x").decode()], "request_id": "r"},
    )
    out = await call_tool(
        make_server(tts),
        "sarvam_tools_tts_speak",
        text="hi",
        target_language_code="hi-IN",
        output_audio_codec="mp3",
        temperature=0.4,
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["output_audio_codec"] == "mp3" and body["temperature"] == 0.4
    assert out["file_path"].endswith(".mp3")


async def test_tts_default_body_unchanged(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/text-to-speech",
        json={"audios": [base64.b64encode(b"x").decode()], "request_id": "r"},
    )
    await call_tool(
        make_server(tts), "sarvam_tools_tts_speak", text="hi", target_language_code="hi-IN"
    )
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert "output_audio_codec" not in body and "temperature" not in body


async def test_tts_opus_at_22050_rejected(make_server, httpx_mock):
    with pytest.raises(ToolError, match="opus"):
        await call_tool(
            make_server(tts),
            "sarvam_tools_tts_speak",
            text="hi",
            target_language_code="hi-IN",
            output_audio_codec="opus",
            speech_sample_rate=22050,
        )
    assert httpx_mock.get_requests() == []


async def test_transliterate_numerals_language_is_english_or_native(make_server, httpx_mock):
    httpx_mock.add_response(
        url="https://api.sarvam.ai/transliterate",
        json={"transliterated_text": "x", "source_language_code": "hi-IN"},
    )
    await call_tool(
        make_server(transliterate),
        "sarvam_tools_transliterate",
        input="12",
        source_language_code="hi-IN",
        target_language_code="en-IN",
        spoken_form=True,
        spoken_form_numerals_language="english",
    )
    assert (
        json.loads(httpx_mock.get_requests()[0].content)["spoken_form_numerals_language"]
        == "english"
    )
    with pytest.raises(ToolError):
        await call_tool(
            make_server(transliterate),
            "sarvam_tools_transliterate",
            input="12",
            source_language_code="hi-IN",
            target_language_code="en-IN",
            spoken_form_numerals_language="hi-IN",
        )
