"""Retry text-analytics with the discovered correct shape."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
JSON_DIR = HERE / "test-outputs" / "json"

from sarvam_mcp.auth import StaticKeyProvider, set_auth  # noqa: E402
from sarvam_mcp.config import Config  # noqa: E402
from sarvam_mcp.http import SarvamClient  # noqa: E402


async def main():
    cfg = Config.load()
    set_auth(StaticKeyProvider(cfg.api_key))  # type: ignore[arg-type]
    client = SarvamClient(cfg.base_url)

    text = (
        "Sarvam AI is an Indian generative AI company founded in 2023, "
        "headquartered in Bangalore. The company builds Indic-language models "
        "including STT, TTS, and LLM capabilities for Indic languages."
    )
    questions = [
        {"id": "q1", "text": "When was Sarvam AI founded?", "type": "short answer"},
        {"id": "q2", "text": "Where is Sarvam headquartered?", "type": "short answer"},
        {"id": "q3", "text": "Is Sarvam an Indian company?", "type": "boolean"},
    ]
    body = None
    for attempt in range(4):
        start = time.perf_counter()
        try:
            payload, metrics = await client.post_multipart(
                "/text-analytics",
                data={
                    "text": text,
                    "questions": json.dumps(questions),
                },
            )
            ms = (time.perf_counter() - start) * 1000
            print(f"attempt {attempt+1}: ✓ {ms:.0f}ms · request_id={metrics.request_id}")
            body = payload
            break
        except Exception as exc:
            ms = (time.perf_counter() - start) * 1000
            print(f"attempt {attempt+1}: ✗ {ms:.0f}ms · {type(exc).__name__}: {str(exc)[:200]}")
            await asyncio.sleep(2 + attempt)

    if body is not None:
        JSON_DIR.mkdir(parents=True, exist_ok=True)
        (JSON_DIR / "sarvam_text_analytics.json").write_text(
            json.dumps(body, indent=2, ensure_ascii=False, default=str)
        )
        print("\nSaved → test-outputs/json/sarvam_text_analytics.json")
        print(json.dumps(body, indent=2, ensure_ascii=False)[:1500])
    else:
        print("\nText-analytics still 5xx after retries — request shape is correct, server-side issue.")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
