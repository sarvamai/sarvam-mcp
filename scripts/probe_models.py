"""Probe which model versions the live API accepts on this key."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from sarvam_mcp.auth import StaticKeyProvider, set_auth
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient

HERE = Path(__file__).resolve().parent.parent
WAV = HERE / "test-outputs" / "audio" / "tts_speak.wav"


async def probe(label: str, coro):
    start = time.perf_counter()
    try:
        body, _ = await coro
        ms = (time.perf_counter() - start) * 1000
        print(f"  ✓ {label}  ({ms:.0f}ms)")
        return True
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        print(f"  ✗ {label}  → {type(exc).__name__}: {str(exc)[:140]}")
        return False


async def main():
    cfg = Config.load()
    set_auth(StaticKeyProvider(cfg.api_key))  # type: ignore[arg-type]
    c = SarvamClient(cfg.base_url, region=cfg.region)

    print("\n=== TTS (bulbul tags) ===")
    for v in ["bulbul:v3"]:
        await probe(
            v,
            c.post_json(
                "/text-to-speech",
                json_body={
                    "inputs": ["नमस्ते"],
                    "target_language_code": "hi-IN",
                    "speaker": "priya",
                    "speech_sample_rate": 24000,
                    "model": v,
                },
            ),
        )

    print("\n=== STT transcribe — saaras ===")
    if WAV.exists():
        wav = WAV.read_bytes()
        for v in ["saaras:v3"]:
            await probe(
                v,
                c.post_multipart(
                    "/speech-to-text",
                    data={
                        "model": v,
                        "language_code": "hi-IN",
                        "with_timestamps": "false",
                        "mode": "transcribe",
                    },
                    files={"file": ("c.wav", wav, "audio/wav")},
                ),
            )
    else:
        print("  (no test wav — skipping)")

    print("\n=== STT translate — Saaras ===")
    if WAV.exists():
        wav = WAV.read_bytes()
        for v in ["saaras:v3", "saaras:v2.5", "saaras:v2", "saaras:v1", "saaras:flash"]:
            await probe(
                v,
                c.post_multipart(
                    "/speech-to-text-translate",
                    data={"model": v, "with_diarization": "false"},
                    files={"file": ("c.wav", wav, "audio/wav")},
                ),
            )
    else:
        print("  (no test wav — skipping)")

    print("\n=== Translate — Mayura ===")
    for v in ["mayura:v2", "mayura:v1", "mayura"]:
        await probe(
            v,
            c.post_json(
                "/translate",
                json_body={
                    "input": "Hello",
                    "source_language_code": "en-IN",
                    "target_language_code": "hi-IN",
                    "model": v,
                    "mode": "formal",
                },
            ),
        )

    print("\n=== Translate — Sarvam-Translate ===")
    for v in ["sarvam-translate:v2", "sarvam-translate:v1", "sarvam-translate"]:
        await probe(
            v,
            c.post_json(
                "/translate",
                json_body={
                    "input": "Hello",
                    "source_language_code": "en-IN",
                    "target_language_code": "ta-IN",
                    "model": v,
                },
            ),
        )

    print("\n=== LLM (chat) ===")
    for v in ["sarvam-105b", "sarvam-30b", "sarvam-2b"]:
        await probe(
            v,
            c.post_json(
                "/v1/chat/completions",
                json_body={
                    "model": v,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
            ),
        )

    await c.aclose()


if __name__ == "__main__":
    asyncio.run(main())
