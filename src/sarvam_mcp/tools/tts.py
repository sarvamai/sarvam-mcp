"""Text-to-speech tools — speak (REST) + stream (WebSocket)."""

from __future__ import annotations

import base64
import time
import uuid
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import BulbulSpeaker, TtsLanguageCode, log_tool_error, ready_ctx

TTS_PATH = "/text-to-speech"
TTS_STREAM_PATH = "/text-to-speech/stream"  # documented WebSocket path

SampleRate = Literal[8000, 16000, 22050, 24000, 32000, 44100, 48000]
TtsModel = Literal["bulbul:v3"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_tts_speak",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Generate speech from text (model bulbul:v3). 11 Indic languages.\n\n"
            "Speaker hints (v3 voice roster):\n"
            "  • `priya` / `neha` / `pooja` — warm friendly female (default `priya`)\n"
            "  • `aditya` / `rahul` / `kabir` — professional male\n"
            "  • `shreya` / `kavya` / `ritu` — calm news-anchor female\n"
            "  • `vijay` / `gokul` / `anand` — mature authoritative male\n"
            "  • `tanya` / `suhani` / `niharika` — young energetic female\n\n"
            "The audio file is written under SARVAM_MCP_BASE_PATH (default ~/Desktop)."
        ),
    )
    async def sarvam_tts_speak(
        ctx: Context,
        text: str = Field(description="The text to synthesize. Up to ~500 chars per call."),
        target_language_code: TtsLanguageCode = Field(
            description="Output language. TTS supports 11 Indic languages.",
        ),
        speaker: BulbulSpeaker = Field(
            default="priya",
            description="Voice. Default `priya` — use `sarvam_code_speakers` for the full v3 list.",
        ),
        speech_sample_rate: SampleRate = Field(
            default=24000, description="PCM sample rate of the output WAV."
        ),
        pitch: float = Field(default=0.0, ge=-1.0, le=1.0),
        pace: float = Field(default=1.0, ge=0.3, le=3.0),
        loudness: float = Field(default=1.0, ge=0.1, le=3.0),
        enable_preprocessing: bool = Field(
            default=True,
            description="Normalize numbers/dates/code-mixed segments before synthesis.",
        ),
        model: TtsModel = Field(
            default="bulbul:v3",
            description="`bulbul:v3` (recommended TTS model).",
        ),
    ) -> dict[str, Any]:
        try:
            sc = await ready_ctx(ctx)
            body: dict[str, Any] = {
                "inputs": [text],
                "target_language_code": target_language_code,
                "speaker": speaker,
                "speech_sample_rate": speech_sample_rate,
                "pitch": pitch,
                "pace": pace,
                "loudness": loudness,
                "enable_preprocessing": enable_preprocessing,
                "model": model,
            }

            with measure_tool() as metrics:
                payload, call = await sc.client.post_json(TTS_PATH, json_body=body)
                metrics.merge(call)

            audios = payload.get("audios") or []
            if not audios:
                raise RuntimeError(f"TTS response had no audio. Raw: {payload!r}")
            wav_bytes = base64.b64decode(audios[0])

            filename = f"sarvam-tts-{uuid.uuid4().hex[:8]}.wav"
            stored = await sc.audio_sink.store(
                wav_bytes, filename=filename, mime_type="audio/wav"
            )

            return {
                "file_path": stored.file_path,
                "resource_uri": stored.resource_uri,
                "base64_data": stored.base64_data,
                "mime_type": stored.mime_type,
                "size_bytes": stored.size_bytes,
                "speaker": speaker,
                "language": target_language_code,
                "observability": metrics.to_response_block(),
            }
        except Exception as exc:
            log_tool_error("sarvam_tools_tts_speak", exc)
            raise

    @mcp.tool(
        name="sarvam_tools_tts_stream",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Streaming variant of sarvam_tts_speak using the TTS WebSocket. "
            "Audio is streamed to disk in the background; the tool returns a "
            "sarvam:// resource URI immediately."
        ),
    )
    async def sarvam_tts_stream(
        ctx: Context,
        text: str = Field(description="Text to synthesize."),
        target_language_code: TtsLanguageCode = Field(),
        speaker: BulbulSpeaker = Field(default="priya"),
        speech_sample_rate: SampleRate = Field(default=24000),
        model: TtsModel = Field(default="bulbul:v3"),
    ) -> dict[str, Any]:
        try:
            return await _tts_stream_impl(ctx, text, target_language_code, speaker, speech_sample_rate, model)
        except Exception as exc:
            log_tool_error("sarvam_tools_tts_stream", exc)
            raise

    async def _tts_stream_impl(ctx, text, target_language_code, speaker, speech_sample_rate, model):
        sc = await ready_ctx(ctx)
        ws_url = sc.config.base_url.replace("http", "ws", 1) + TTS_STREAM_PATH

        chunks: list[bytes] = []
        with measure_tool() as metrics:
            try:
                async with sc.client.stream_ws(ws_url) as ws:
                    await ws.send(
                        _ws_request_payload(
                            text=text,
                            target_language_code=target_language_code,
                            speaker=speaker,
                            speech_sample_rate=speech_sample_rate,
                            model=model,
                        )
                    )
                    async for frame in ws:
                        if isinstance(frame, bytes):
                            chunks.append(frame)
                        else:
                            event = _maybe_parse_event(frame)
                            if event.get("type") == "end":
                                break
                            if event.get("audio"):
                                chunks.append(base64.b64decode(event["audio"]))
            except Exception as exc:  # noqa: BLE001
                # Fall back to REST if streaming endpoint is unavailable.
                await ctx.warning(
                    f"WebSocket streaming failed ({exc!r}); falling back to REST."
                )
                rest_resp = await sc.client.post_json(
                    TTS_PATH,
                    json_body={
                        "inputs": [text],
                        "target_language_code": target_language_code,
                        "speaker": speaker,
                        "speech_sample_rate": speech_sample_rate,
                        "model": model,
                    },
                )
                payload, call = rest_resp
                metrics.merge(call)
                audios = payload.get("audios") or []
                chunks = [base64.b64decode(audios[0])] if audios else []

        wav_bytes = b"".join(chunks)
        if not wav_bytes:
            raise RuntimeError("TTS stream produced no audio.")

        filename = f"sarvam-tts-stream-{uuid.uuid4().hex[:8]}.wav"
        stored = await sc.audio_sink.store(
            wav_bytes, filename=filename, mime_type="audio/wav"
        )

        return {
            "file_path": stored.file_path,
            "resource_uri": stored.resource_uri,
            "size_bytes": stored.size_bytes,
            "completed_at": time.time(),
            "observability": metrics.to_response_block(),
        }


def _ws_request_payload(
    *,
    text: str,
    target_language_code: str,
    speaker: str,
    speech_sample_rate: int,
    model: str,
) -> str:
    import json as _json

    return _json.dumps(
        {
            "type": "synthesize",
            "text": text,
            "target_language_code": target_language_code,
            "speaker": speaker,
            "speech_sample_rate": speech_sample_rate,
            "model": model,
        }
    )


def _maybe_parse_event(frame: str) -> dict[str, Any]:
    import json as _json

    try:
        result = _json.loads(frame)
        return result if isinstance(result, dict) else {}
    except _json.JSONDecodeError:
        return {}
