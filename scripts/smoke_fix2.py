"""Second pass — narrowing down text-analytics question format and vision path."""

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
        print(f"  ✗ FAILED in {ms:.0f}ms · {type(exc).__name__}: {exc}")
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

    # ── TEXT ANALYTICS — questions as list of dicts ────────────────────
    print("=== TEXT ANALYTICS — questions=list of dicts ===")

    # Variant A: questions as JSON list of {id, text}
    body, _ = await try_call(
        'multipart questions=[{id,text},...] (JSON-stringified)',
        client.post_multipart(
            "/text-analytics",
            data={
                "text": "Sarvam AI is an Indian AI startup founded in 2023, focused on Indic languages.",
                "questions": json.dumps(
                    [
                        {"id": "q1", "text": "When was Sarvam AI founded?"},
                        {"id": "q2", "text": "What languages does Sarvam focus on?"},
                    ]
                ),
            },
        ),
    )
    if body is None:
        # Variant B: questions as list of dicts via JSON body
        body, _ = await try_call(
            'JSON {text, questions=[{id,text},...]}',
            client.post_json(
                "/text-analytics",
                json_body={
                    "text": "Sarvam AI is an Indian AI startup founded in 2023.",
                    "questions": [
                        {"id": "q1", "text": "When was Sarvam founded?"},
                        {"id": "q2", "text": "What does Sarvam build?"},
                    ],
                },
            ),
        )
    if body is None:
        # Variant C: questions=[{question: ...}]
        body, _ = await try_call(
            'multipart questions=[{question}]',
            client.post_multipart(
                "/text-analytics",
                data={
                    "text": "Sarvam is an Indian AI startup.",
                    "questions": json.dumps(
                        [{"question": "Where is Sarvam based?"}]
                    ),
                },
            ),
        )
    if body is None:
        # Variant D: text + question (single, multipart)
        body, _ = await try_call(
            'multipart {text, question}',
            client.post_multipart(
                "/text-analytics",
                data={
                    "text": "Sarvam is an Indian AI startup.",
                    "question": "Where is Sarvam based?",
                },
            ),
        )
    if body is not None:
        write_json("sarvam_text_analytics", body)

    # ── VISION — empirical path search ─────────────────────────────────
    print("\n=== VISION — broader path search ===")
    img_path = DOCS_DIR / "hello.png"
    if not img_path.exists():
        print("  no test image; skipping")
    else:
        img_bytes = img_path.read_bytes()
        candidates = [
            ("POST", "/parsedoc"),
            ("POST", "/parse-doc"),
            ("POST", "/parse_doc"),
            ("POST", "/parse/doc"),
            ("POST", "/document-parse"),
            ("POST", "/extract"),
            ("POST", "/document/extract"),
            ("POST", "/v1/document"),
            ("POST", "/v1/parse"),
            ("POST", "/v1/parse-doc"),
            ("POST", "/v1/parsedoc"),
            ("POST", "/api/v1/parse"),
        ]
        success_path = None
        for method, path in candidates:
            body, _ = await try_call(
                f"vision: {method} {path}",
                client.post_multipart(
                    path,
                    data={"output_format": "markdown"},
                    files={"file": ("hello.png", img_bytes, "image/png")},
                ),
            )
            if body is not None:
                write_json("sarvam_vision_extract", body)
                success_path = path
                break
        if success_path:
            print(f"\n  ★ working vision path: {success_path}")
        else:
            print("\n  no vision path responded — confirming endpoint may not be GA on this account")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
