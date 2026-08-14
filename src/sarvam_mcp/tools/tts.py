"""Text-to-speech tools — speak (REST) + stream (WebSocket)."""

from __future__ import annotations

import asyncio
import base64
import time
import uuid
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import BulbulSpeaker, TtsLanguageCode, ready_ctx

TTS_PATH = "/text-to-speech"
TTS_STREAM_PATH = "/text-to-speech/ws"  # current WebSocket path — live-confirmed 2026-08-14.
# The old "/text-to-speech/stream" path used to live here now returns HTTP 403
# at the WebSocket handshake, before a single message is sent.

# Idle time with no new frame from the server before we consider the stream
# finished — the WS protocol has no reliable "done" event (send_completion_event
# didn't produce one in live testing either), so this is a timeout heuristic,
# same as the one described in Sarvam's own docs.
WS_IDLE_TIMEOUT_SECONDS = 8.0
WS_MAX_STREAM_SECONDS = 60.0

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
        pace: float = Field(default=1.0, ge=0.3, le=3.0),
        enable_preprocessing: bool = Field(
            default=True,
            description="Normalize numbers/dates/code-mixed segments before synthesis.",
        ),
        model: TtsModel = Field(
            default="bulbul:v3",
            description="`bulbul:v3` (recommended TTS model).",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        # bulbul:v3 rejects requests that include pitch/loudness at all
        # ("Pitch and loudness parameters are currently not supported for
        # the Bulbul V3 model") — live-confirmed 2026-08-13. Don't send them.
        body: dict[str, Any] = {
            "inputs": [text],
            "target_language_code": target_language_code,
            "speaker": speaker,
            "speech_sample_rate": speech_sample_rate,
            "pace": pace,
            "enable_preprocessing": enable_preprocessing,
            "model": model,
        }

        with measure_tool() as metrics:
            payload, call = await sc.client.post_json(TTS_PATH, json_body=body)
            metrics.merge(call)

        # Sarvam returns: {"audios": ["<base64-wav>", ...], "request_id": "..."}
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

    @mcp.tool(
        name="sarvam_tools_tts_stream",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Streaming variant of sarvam_tts_speak using the TTS WebSocket. "
            "Opens a connection, sends the text once, and collects the streamed "
            "audio chunks into a single WAV file (there's no reliable server-side "
            "'done' signal, so completion is detected via a short idle timeout — "
            "expect a few extra seconds of latency vs. sarvam_tts_speak for that "
            "reason). Falls back to the REST endpoint if the WebSocket is "
            "unavailable."
        ),
    )
    async def sarvam_tts_stream(
        ctx: Context,
        text: str = Field(description="Text to synthesize."),
        target_language_code: TtsLanguageCode = Field(),
        speaker: BulbulSpeaker = Field(default="priya"),
        pace: float = Field(default=1.0, ge=0.3, le=3.0),
        model: TtsModel = Field(default="bulbul:v3"),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        ws_url = f"{sc.config.base_url.replace('http', 'ws', 1)}{TTS_STREAM_PATH}?model={model}"

        chunks: list[bytes] = []
        with measure_tool() as metrics:
            try:
                async with sc.client.stream_ws(ws_url) as ws:
                    await ws.send(
                        _ws_config_payload(
                            speaker=speaker, language_code=target_language_code, pace=pace
                        )
                    )
                    await ws.send(_ws_text_payload(text))
                    await ws.send(_ws_flush_payload())

                    loop = asyncio.get_event_loop()
                    deadline = loop.time() + WS_MAX_STREAM_SECONDS
                    while loop.time() < deadline:
                        try:
                            frame = await asyncio.wait_for(
                                ws.recv(), timeout=WS_IDLE_TIMEOUT_SECONDS
                            )
                        except TimeoutError:
                            break  # no new audio for a while — treat as done
                        if isinstance(frame, bytes):
                            chunks.append(frame)
                            continue
                        event = _maybe_parse_event(frame)
                        event_type = event.get("type")
                        if event_type == "audio":
                            audio_b64 = (event.get("data") or {}).get("audio")
                            if audio_b64:
                                chunks.append(base64.b64decode(audio_b64))
                        elif event_type == "event":
                            if (event.get("data") or {}).get("event_type") == "final":
                                break
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
                        "speech_sample_rate": 24000,
                        "pace": pace,
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
        wav_bytes = _finalize_wav_header(wav_bytes)

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


def _ws_config_payload(*, speaker: str, language_code: str, pace: float) -> str:
    import json as _json

    return _json.dumps(
        {
            "type": "config",
            "data": {
                "speaker": speaker,
                "language_code": language_code,
                "pace": pace,
                "output_audio_codec": "wav",
            },
        }
    )


def _ws_text_payload(text: str) -> str:
    import json as _json

    return _json.dumps({"type": "text", "data": {"text": text}})


def _ws_flush_payload() -> str:
    import json as _json

    return _json.dumps({"type": "flush"})


def _finalize_wav_header(wav_bytes: bytes) -> bytes:
    """Patch the RIFF/data chunk sizes once the full stream is collected.

    Sarvam's TTS WebSocket streams a WAV whose header doesn't know the final
    length up front, so it fills the RIFF size and ``data`` chunk size fields
    with the streaming placeholder ``0xFFFFFFFF``. That's fine for a live
    stream but produces a file some WAV parsers read incorrectly (e.g.
    Python's own ``wave`` module reports a ~27-hour duration for a 5-second
    clip) — live-confirmed 2026-08-14. Rewrite both fields now that the true
    size is known.
    """
    import struct

    if len(wav_bytes) < 44 or wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        return wav_bytes
    patched = bytearray(wav_bytes)
    patched[4:8] = struct.pack("<I", len(wav_bytes) - 8)
    data_offset = wav_bytes.find(b"data")
    if data_offset != -1 and data_offset + 8 <= len(wav_bytes):
        patched[data_offset + 4 : data_offset + 8] = struct.pack(
            "<I", len(wav_bytes) - (data_offset + 8)
        )
    return bytes(patched)


def _maybe_parse_event(frame: str) -> dict[str, Any]:
    import json as _json

    try:
        result = _json.loads(frame)
        return result if isinstance(result, dict) else {}
    except _json.JSONDecodeError:
        return {}
