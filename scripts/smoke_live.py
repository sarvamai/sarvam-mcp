"""Live end-to-end smoke test against the real Sarvam API.

Hits every atomic tool's underlying endpoint, captures the raw response,
and writes audio/document outputs to disk under ``test-outputs/``.

Usage:
    SARVAM_API_KEY=sk_... python scripts/smoke_live.py

Outputs:
    test-outputs/
    ├── json/<tool>.json         # raw response payloads
    ├── audio/<tool>.wav         # generated speech
    └── SUMMARY.md               # written manually after running
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Make sure these are set BEFORE importing sarvam_mcp.
HERE = Path(__file__).resolve().parent.parent
OUT_DIR = HERE / "test-outputs"
JSON_DIR = OUT_DIR / "json"
AUDIO_DIR = OUT_DIR / "audio"
DOCS_DIR = OUT_DIR / "documents"

os.environ.setdefault("SARVAM_MCP_BASE_PATH", str(AUDIO_DIR))
os.environ.setdefault("SARVAM_AUDIO_OUTPUT_MODE", "files")

from sarvam_mcp.auth import StaticKeyProvider, set_auth  # noqa: E402
from sarvam_mcp.config import Config  # noqa: E402
from sarvam_mcp.http import SarvamClient  # noqa: E402


@dataclass
class Result:
    name: str
    ok: bool
    latency_ms: float
    request_id: str | None = None
    note: str = ""
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def write_json(name: str, payload: Any) -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    path = JSON_DIR / f"{name}.json"
    if isinstance(payload, (bytes, bytearray)):
        path.with_suffix(".bin").write_bytes(payload)
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


async def run_one(name: str, coro):
    print(f"\n→ {name}")
    start = time.perf_counter()
    try:
        result = await coro
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  ✓ ok in {elapsed:.0f}ms")
        return result, elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  ✗ FAILED in {elapsed:.0f}ms — {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return None, elapsed


async def main() -> None:
    if not os.environ.get("SARVAM_API_KEY"):
        raise SystemExit("SARVAM_API_KEY not set in env")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    cfg = Config.load()
    set_auth(StaticKeyProvider(cfg.api_key))  # type: ignore[arg-type]
    client = SarvamClient(cfg.base_url, region=cfg.region)
    print(f"Sarvam MCP smoke · base_url={cfg.base_url} region={cfg.region}")

    results: list[Result] = []

    # ── 1. Language identification ──────────────────────────────────────
    name = "sarvam_identify_language"
    payload, ms = await run_one(
        name,
        client.post_json(
            "/text-lid", json_body={"input": "नमस्ते, आप कैसे हैं?"}
        ),
    )
    if payload is not None:
        body, metrics = payload
        write_json(name, body)
        results.append(
            Result(
                name=name,
                ok=True,
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"detected: {body.get('language_code')} / {body.get('script_code')}",
            )
        )
    else:
        results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))

    # ── 2. Translate (Mayura) ───────────────────────────────────────────
    name = "sarvam_translate_mayura"
    payload, ms = await run_one(
        name,
        client.post_json(
            "/translate",
            json_body={
                "input": "Hello, how are you doing today?",
                "source_language_code": "en-IN",
                "target_language_code": "hi-IN",
                "model": "mayura:v1",
                "mode": "modern-colloquial",
                "numerals_format": "international",
                "enable_preprocessing": True,
            },
        ),
    )
    hindi_text = "नमस्ते, आज आप कैसे हैं?"  # fallback
    if payload is not None:
        body, metrics = payload
        write_json(name, body)
        if body.get("translated_text"):
            hindi_text = body["translated_text"]
        results.append(
            Result(
                name=name,
                ok=True,
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"hi: {body.get('translated_text', '')[:80]}",
            )
        )
    else:
        results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))

    # ── 3. Translate (Sarvam-Translate, 22-lang) ───────────────────────
    name = "sarvam_translate_sarvam"
    payload, ms = await run_one(
        name,
        client.post_json(
            "/translate",
            json_body={
                "input": "Artificial intelligence is changing the world.",
                "source_language_code": "en-IN",
                "target_language_code": "ta-IN",
                "model": "sarvam-translate:v1",
                "numerals_format": "international",
            },
        ),
    )
    if payload is not None:
        body, metrics = payload
        write_json(name, body)
        results.append(
            Result(
                name=name,
                ok=True,
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"ta: {body.get('translated_text', '')[:80]}",
            )
        )
    else:
        results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))

    # ── 4. Transliterate ────────────────────────────────────────────────
    name = "sarvam_transliterate"
    payload, ms = await run_one(
        name,
        client.post_json(
            "/transliterate",
            json_body={
                "input": "नमस्ते दुनिया",
                "source_language_code": "hi-IN",
                "target_language_code": "en-IN",
                "numerals_format": "international",
                "spoken_form": False,
            },
        ),
    )
    if payload is not None:
        body, metrics = payload
        write_json(name, body)
        results.append(
            Result(
                name=name,
                ok=True,
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"out: {body.get('transliterated_text', '')[:80]}",
            )
        )
    else:
        results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))

    # ── 5. Text Analytics (multipart, typed questions) ──────────────────
    name = "sarvam_text_analytics"
    payload, ms = await run_one(
        name,
        client.post_multipart(
            "/text-analytics",
            data={
                "text": (
                    "Sarvam AI is an Indian generative AI company founded in "
                    "2023, headquartered in Bangalore. It builds Indic-language "
                    "STT, TTS, and LLM products for Indian languages."
                ),
                "questions": json.dumps(
                    [
                        {"id": "q1", "text": "When was Sarvam founded?", "type": "short answer"},
                        {"id": "q2", "text": "Where is Sarvam HQ?", "type": "short answer"},
                        {"id": "q3", "text": "Is Sarvam Indian?", "type": "boolean"},
                    ]
                ),
            },
        ),
    )
    if payload is not None:
        body, metrics = payload
        write_json(name, body)
        results.append(
            Result(
                name=name,
                ok=True,
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"answers: {len(body.get('answers') or [])}",
            )
        )
    else:
        results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))

    # ── 6. LLM ─────────────────────────────────────────────────────────
    name = "sarvam_llm_complete"
    payload, ms = await run_one(
        name,
        client.post_json(
            "/v1/chat/completions",
            json_body={
                "model": "sarvam-30b",
                "messages": [
                    {"role": "system", "content": "You are a concise Indic-language expert."},
                    {"role": "user", "content": "Translate 'good morning' into Tamil and Marathi."},
                ],
                "temperature": 0.3,
                "max_tokens": 150,
            },
        ),
    )
    if payload is not None:
        body, metrics = payload
        write_json(name, body)
        choice = (body.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "")
        results.append(
            Result(
                name=name,
                ok=True,
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"reply: {content[:120]}",
            )
        )
    else:
        results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))

    # ── 7. TTS (bulbul:v3) ───────────────────────────────────────────────
    name = "sarvam_tts_speak"
    payload, ms = await run_one(
        name,
        client.post_json(
            "/text-to-speech",
            json_body={
                "inputs": [hindi_text],
                "target_language_code": "hi-IN",
                "speaker": "priya",
                "speech_sample_rate": 24000,
                "model": "bulbul:v3",
                "enable_preprocessing": True,
            },
        ),
    )
    tts_wav: bytes = b""
    if payload is not None:
        body, metrics = payload
        # Don't write whole base64 to JSON — strip it for readability.
        slim = {k: v for k, v in body.items() if k != "audios"}
        slim["audios_count"] = len(body.get("audios") or [])
        write_json(name, slim)
        audios = body.get("audios") or []
        if audios:
            tts_wav = base64.b64decode(audios[0])
            (AUDIO_DIR / "tts_speak.wav").write_bytes(tts_wav)
        results.append(
            Result(
                name=name,
                ok=bool(tts_wav),
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"wrote {len(tts_wav)} bytes to test-outputs/audio/tts_speak.wav",
            )
        )
    else:
        results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))

    # ── 8. STT — round-trip the TTS audio ───────────────────────────────
    name = "sarvam_stt_transcribe"
    if tts_wav:
        wav_path = AUDIO_DIR / "tts_speak.wav"
        files = {"file": (wav_path.name, wav_path.read_bytes(), "audio/wav")}
        data = {
            "model": "saaras:v3",
            "language_code": "hi-IN",
            "with_timestamps": "false",
            "mode": "transcribe",
        }
        payload, ms = await run_one(
            name,
            client.post_multipart("/speech-to-text", data=data, files=files),
        )
        if payload is not None:
            body, metrics = payload
            write_json(name, body)
            results.append(
                Result(
                    name=name,
                    ok=True,
                    latency_ms=ms,
                    request_id=metrics.request_id,
                    note=f"transcript: {(body.get('transcript') or '')[:120]}",
                )
            )
        else:
            results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))
    else:
        results.append(
            Result(
                name=name,
                ok=False,
                latency_ms=0,
                error="skipped — no TTS audio to feed in",
            )
        )

    # ── 9. STT translate (audio → English text) ─────────────────────────
    name = "sarvam_stt_translate"
    if tts_wav:
        wav_path = AUDIO_DIR / "tts_speak.wav"
        files = {"file": (wav_path.name, wav_path.read_bytes(), "audio/wav")}
        data = {"model": "saaras:v3", "with_diarization": "false"}
        payload, ms = await run_one(
            name,
            client.post_multipart("/speech-to-text-translate", data=data, files=files),
        )
        if payload is not None:
            body, metrics = payload
            write_json(name, body)
            results.append(
                Result(
                    name=name,
                    ok=True,
                    latency_ms=ms,
                    request_id=metrics.request_id,
                    note=f"english: {(body.get('transcript') or '')[:120]}",
                )
            )
        else:
            results.append(Result(name=name, ok=False, latency_ms=ms, error="see traceback"))
    else:
        results.append(
            Result(name=name, ok=False, latency_ms=0, error="skipped — no audio")
        )

    # ── 10. STT batch — JSON init returns Azure SAS upload + output URLs ─
    name = "sarvam_stt_batch_submit"
    payload, ms = await run_one(
        name,
        client.post_json(
            "/speech-to-text/job/init",
            json_body={"model": "saaras:v3", "with_timestamps": False},
        ),
    )
    if payload is not None:
        body, metrics = payload
        write_json(name, body)
        results.append(
            Result(
                name=name,
                ok=True,
                latency_ms=ms,
                request_id=metrics.request_id,
                note=f"job_id={body.get('job_id')} · returned Azure upload + output SAS URLs",
            )
        )
    else:
        results.append(
            Result(
                name=name,
                ok=False,
                latency_ms=ms,
                error="endpoint may differ — verify exact batch path with docs",
            )
        )

    # ── 11. Vision — extract from a tiny synthesized PNG ────────────────
    name = "sarvam_vision_extract"
    test_img = DOCS_DIR / "hello.png"
    try:
        _make_text_image(test_img, "Sarvam MCP test")
        with test_img.open("rb") as fh:
            files = {"file": (test_img.name, fh.read(), "image/png")}
        data = {"output_format": "markdown", "language_code": "en-IN"}
        payload, ms = await run_one(
            name,
            client.post_multipart("/parse/parsedoc", data=data, files=files),
        )
        if payload is not None:
            body, metrics = payload
            write_json(name, body if isinstance(body, dict) else {"raw": str(body)[:1000]})
            results.append(
                Result(
                    name=name,
                    ok=True,
                    latency_ms=ms,
                    request_id=metrics.request_id,
                    note="vision endpoint responded — verify content shape in JSON",
                )
            )
        else:
            results.append(
                Result(
                    name=name,
                    ok=False,
                    latency_ms=ms,
                    error="endpoint path may differ — try /parse or /document/parse",
                )
            )
    except Exception as exc:
        results.append(
            Result(name=name, ok=False, latency_ms=0, error=f"setup failed: {exc!r}")
        )

    # ── Save consolidated results ──────────────────────────────────────
    summary_payload = [asdict(r) for r in results]
    (JSON_DIR / "_summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False)
    )

    print("\n" + "=" * 60)
    print(f"{'TOOL':<30} {'OK':<5} {'MS':>6}  REQUEST_ID")
    print("-" * 60)
    for r in results:
        ok = "✓" if r.ok else "✗"
        print(f"{r.name:<30} {ok:<5} {int(r.latency_ms):>6}  {r.request_id or '-'}")
    print("=" * 60)
    print(f"\nDetails: {JSON_DIR}/_summary.json")

    await client.aclose()


def _make_text_image(path: Path, text: str) -> None:
    """Render a tiny PNG with text. Falls back to a 1×1 placeholder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError:
        # Minimal valid PNG (8×8 white). Vision will still respond.
        path.write_bytes(
            bytes.fromhex(
                "89504E470D0A1A0A0000000D49484452000000080000000808060000"
                "00C40FBE8B0000001D49444154789C636060606060606060606060606"
                "060606060000000FFFF030000060001E5E97D7B0000000049454E44AE"
                "426082"
            )
        )
        return
    img = Image.new("RGB", (320, 80), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), text, fill="black")
    img.save(path, "PNG")


if __name__ == "__main__":
    asyncio.run(main())
