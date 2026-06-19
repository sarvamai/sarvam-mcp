"""Re-test the three tools that failed on first pass with corrected request shapes.

Failures from the first run:
1. /text-analytics      → 'body.text : Field required'  → likely multipart, not JSON
2. /speech-to-text/job/init → 'body : Input should be valid dict'  → endpoint shape differs
3. /parse/parsedoc      → 'Not Found'                   → wrong path

Try alternates and capture whichever shape works.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT_DIR = HERE / "test-outputs"
JSON_DIR = OUT_DIR / "json"
AUDIO_DIR = OUT_DIR / "audio"
DOCS_DIR = OUT_DIR / "documents"

os.environ.setdefault("SARVAM_MCP_BASE_PATH", str(AUDIO_DIR))

from sarvam_mcp.auth import StaticKeyProvider, set_auth  # noqa: E402
from sarvam_mcp.config import Config  # noqa: E402
from sarvam_mcp.http import SarvamClient  # noqa: E402


async def try_call(label: str, coro):
    print(f"\n→ {label}")
    start = time.perf_counter()
    try:
        body, metrics = await coro
        ms = (time.perf_counter() - start) * 1000
        print(f"  ✓ ok in {ms:.0f}ms · request_id={metrics.request_id}")
        return body, metrics, ms
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        print(f"  ✗ FAILED in {ms:.0f}ms · {type(exc).__name__}: {exc}")
        return None, None, ms


def write_json(name: str, payload):
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, dict):
        # Strip giant base64 fields if any.
        payload = {k: v for k, v in payload.items() if not (isinstance(v, str) and len(v) > 5000)}
    (JSON_DIR / f"{name}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    )


async def main():
    cfg = Config.load()
    set_auth(StaticKeyProvider(cfg.api_key))  # type: ignore[arg-type]
    client = SarvamClient(cfg.base_url)

    # ── 1. text-analytics — try multipart with stringified questions ───
    print("\n=== TEXT ANALYTICS attempts ===")

    # 1a. multipart, questions as JSON array string
    body, _, _ = await try_call(
        "text-analytics multipart (questions=JSON string)",
        client.post_multipart(
            "/text-analytics",
            data={
                "text": "Sarvam AI is an Indian AI startup founded in 2023, focused on Indic languages.",
                "questions": json.dumps(
                    [
                        "When was Sarvam AI founded?",
                        "What languages does Sarvam focus on?",
                    ]
                ),
            },
        ),
    )
    if body is None:
        # 1b. JSON body but with array of strings (current shape, retry to confirm)
        body, _, _ = await try_call(
            "text-analytics JSON {text, questions}",
            client.post_json(
                "/text-analytics",
                json_body={
                    "text": "Sarvam AI is an Indian AI startup focused on Indic languages.",
                    "questions": ["When was Sarvam founded?", "What does Sarvam build?"],
                },
            ),
        )
    if body is None:
        # 1c. Try /text-analytics endpoint with `inputs` shape (some Sarvam APIs use this)
        body, _, _ = await try_call(
            "text-analytics multipart {text, questions=newline-list}",
            client.post_multipart(
                "/text-analytics",
                data={
                    "text": "Sarvam AI is an Indian AI startup focused on Indic languages.",
                    "questions": "When was Sarvam founded?\nWhat does Sarvam build?",
                },
            ),
        )
    if body is not None:
        write_json("sarvam_text_analytics", body)

    # ── 2. STT batch — try several documented paths ────────────────────
    print("\n=== STT BATCH attempts ===")
    wav_path = AUDIO_DIR / "tts_speak.wav"
    if not wav_path.exists():
        print("  (skipping — no tts_speak.wav available)")
    else:
        wav_bytes = wav_path.read_bytes()

        # 2a. JSON-only init: register a job and get an upload URL.
        body, _, _ = await try_call(
            "/speech-to-text/job/init  (JSON)",
            client.post_json(
                "/speech-to-text/job/init",
                json_body={
                    "model": "saaras:v3",
                    "with_timestamps": False,
                },
            ),
        )
        if body is None:
            # 2b. Try a GET-based init (some Sarvam batch APIs use GET)
            body, _, _ = await try_call(
                "/speech-to-text/job/init  (GET)",
                client.get_json("/speech-to-text/job/init"),
            )
        if body is None:
            # 2c. Try alternative path
            body, _, _ = await try_call(
                "/speech-to-text-batch  (multipart)",
                client.post_multipart(
                    "/speech-to-text-batch",
                    data={"model": "saaras:v3"},
                    files={"file": ("clip.wav", wav_bytes, "audio/wav")},
                ),
            )
        if body is not None:
            write_json("sarvam_stt_batch_submit", body)

    # ── 3. Vision — try alternate paths ────────────────────────────────
    print("\n=== VISION attempts ===")
    img_path = DOCS_DIR / "hello.png"
    if not img_path.exists():
        print("  (skipping — no test image)")
    else:
        img_bytes = img_path.read_bytes()
        candidates = [
            "/parse/parsedoc",
            "/parse",
            "/document/parse",
            "/parse-document",
            "/v1/parse",
            "/vision/parse",
        ]
        success = False
        for path in candidates:
            body, _, _ = await try_call(
                f"vision: POST {path}  (multipart file=image)",
                client.post_multipart(
                    path,
                    data={"output_format": "markdown", "language_code": "en-IN"},
                    files={"file": ("hello.png", img_bytes, "image/png")},
                ),
            )
            if body is not None:
                write_json("sarvam_vision_extract", body)
                print(f"  ★ working endpoint: {path}")
                success = True
                break
        if not success:
            print("  (none of the vision paths returned 200; needs doc lookup)")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
