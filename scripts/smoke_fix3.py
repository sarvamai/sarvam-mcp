"""Final pass: text-analytics needs questions with `type` field.

Also try Sarvam Vision via alternate base hosts (parse.sarvam.ai etc).
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
DOCS_DIR = OUT_DIR / "documents"

os.environ.setdefault("SARVAM_MCP_BASE_PATH", str(OUT_DIR / "audio"))

import httpx  # noqa: E402

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
        return body, metrics
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        msg = str(exc)
        print(f"  ✗ FAILED in {ms:.0f}ms · {type(exc).__name__}: {msg[:300]}")
        return None, None


def write_json(name: str, payload):
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, dict):
        payload = {k: v for k, v in payload.items() if not (isinstance(v, str) and len(v) > 5000)}
    (JSON_DIR / f"{name}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    )


async def main():
    cfg = Config.load()
    set_auth(StaticKeyProvider(cfg.api_key))  # type: ignore[arg-type]
    client = SarvamClient(cfg.base_url)

    # ── TEXT ANALYTICS — try several `type` values ──────────────────────
    print("=== TEXT ANALYTICS — questions need {id, text, type} ===")

    text = "Sarvam AI is an Indian AI startup founded in 2023, focused on Indic languages."
    success = False
    for qtype in ["short answer", "short-answer", "long answer", "qa", "summary", "boolean", "extractive", "factoid", "open-ended", "multiple-choice"]:
        body, _ = await try_call(
            f"questions type='{qtype}'",
            client.post_multipart(
                "/text-analytics",
                data={
                    "text": text,
                    "questions": json.dumps(
                        [
                            {"id": "q1", "text": "When was Sarvam AI founded?", "type": qtype},
                            {"id": "q2", "text": "What does Sarvam build?", "type": qtype},
                        ]
                    ),
                },
            ),
        )
        if body is not None:
            write_json("sarvam_text_analytics", body)
            print(f"  ★ working type: {qtype!r}")
            success = True
            break

    if not success:
        print("  none of the simple type values worked — likely needs an enum we haven't guessed")

    # ── VISION — try alt hosts ──────────────────────────────────────────
    print("\n=== VISION — alt hosts ===")
    img_path = DOCS_DIR / "hello.png"
    if img_path.exists():
        img_bytes = img_path.read_bytes()
        # Hit alt hostnames directly with bare httpx (bypasses SarvamClient base_url).
        provider = StaticKeyProvider(cfg.api_key)  # type: ignore[arg-type]
        headers = await provider.headers()
        async with httpx.AsyncClient(timeout=30.0) as direct:
            for url in [
                "https://parse.sarvam.ai/parse",
                "https://parse.sarvam.ai/parsedoc",
                "https://parse.sarvam.ai/document/parse",
                "https://api.sarvam.ai/parse-document",
                "https://api.sarvam.ai/v1/document/parse",
                "https://api.sarvam.ai/document-ai/parse",
                "https://api.sarvam.ai/parse/v1",
            ]:
                try:
                    print(f"\n→ direct POST {url}")
                    r = await direct.post(
                        url,
                        headers=headers,
                        files={"file": ("hello.png", img_bytes, "image/png")},
                        data={"output_format": "markdown"},
                    )
                    print(f"  status={r.status_code}  body={r.text[:200]}")
                    if r.status_code < 400:
                        write_json("sarvam_vision_extract", r.json())
                        print(f"  ★ working vision URL: {url}")
                        break
                except Exception as exc:
                    print(f"  exception: {exc!r}")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
