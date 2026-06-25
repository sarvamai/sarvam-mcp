"""STT language-code normalization.

The shared ``LanguageCode`` enum carries two auto-detect tokens: ``"auto"``
(accepted by Translate/Transliterate) and ``"unknown"`` (accepted by STT). The
STT endpoints reject ``"auto"``, so the tools must map it to ``"unknown"`` the
same way ``translate``/``transliterate`` map ``"unknown"`` to ``"auto"``.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio.sinks import FileSink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.server import build_server
from sarvam_mcp.tools.stt import _stt_language_code

# A minimal WAV header so file/MIME handling has something real to chew on.
_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 16


def _fake_ctx(server_ctx: ServerContext) -> SimpleNamespace:
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=server_ctx))


def _form_field(content: bytes, name: str) -> bytes | None:
    m = re.search(rb'name="' + name.encode() + rb'"\r\n\r\n(.*?)\r\n', content, re.DOTALL)
    return m.group(1) if m else None


@pytest.mark.parametrize(
    ("given", "expected"),
    [("auto", "unknown"), ("unknown", "unknown"), ("hi-IN", "hi-IN")],
)
def test_stt_language_code_maps_auto_to_unknown(given: str, expected: str) -> None:
    assert _stt_language_code(given) == expected  # type: ignore[arg-type]


async def test_transcribe_sends_unknown_for_auto(httpx_mock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.sarvam.ai/speech-to-text",
        json={"transcript": "ok", "language_code": "hi-IN"},
    )

    server = build_server()
    server_ctx = ServerContext(
        config=Config(),
        client=SarvamClient("https://api.sarvam.ai"),
        audio_sink=FileSink(tmp_path / "out"),
    )
    tool = await server.get_tool("sarvam_tools_stt_transcribe")

    try:
        await tool.fn(
            ctx=_fake_ctx(server_ctx),
            audio_path=None,
            audio_base64=base64.b64encode(_WAV).decode(),
            audio_url=None,
            filename="clip.wav",
            language_code="auto",
            mode="transcribe",
            with_timestamps=False,
            model="saaras:v3",
            input_audio_codec=None,
        )
    finally:
        await server_ctx.client.aclose()

    request = httpx_mock.get_request()
    assert _form_field(request.content, "language_code") == b"unknown"
