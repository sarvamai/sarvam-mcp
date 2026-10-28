"""Live end-to-end check of the Document AI tools (parse, classify, split).

Drives the real MCP tool functions (through an in-memory FastMCP client) against
the real Sarvam API, using a generated 4-page bundle that holds three documents:

    pages 1-2  tax invoice (page 2 is a continuation)
    page  3    payment receipt
    page  4    purchase order

Usage:
    SARVAM_API_KEY=sk_... python scripts/smoke_doc_ai.py
    python scripts/smoke_doc_ai.py --only classify,split   # subset

Writes raw responses to test-outputs/doc-ai/<case>.json and exits non-zero if
any case fails.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import Client, FastMCP

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio import build_sink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.tools import vision

HERE = Path(__file__).resolve().parent.parent
OUT_DIR = HERE / "test-outputs" / "doc-ai"

CATEGORIES = [
    {"type": "invoice", "description": "A supplier bill listing items, tax and an amount due"},
    {"type": "receipt", "description": "Proof that a payment was received"},
    {"type": "purchase_order", "description": "A buyer's order to a supplier for goods"},
]

PAGES: list[list[str]] = [
    [
        "TAX INVOICE", "Invoice No: INV-1001", "Date: 12 March 2026",
        "Bill To: Acme Traders Pvt Ltd, Pune", "",
        "Item            Qty    Rate      Amount",
        "Steel bolts      100    25.00     2500.00",
        "Copper wire       10   250.00     2500.00", "",
        "Subtotal: 5000.00", "GST 18%: 900.00", "Amount Due: INR 5900.00",
    ],
    [
        "Invoice INV-1001 (continued)", "Page 2 of 2", "",
        "Payment terms: net 30 days from invoice date.",
        "Bank: HDFC Bank, A/c 50100123456789, IFSC HDFC0001234",
        "Late payments attract 2 percent interest per month.",
        "Thank you for your business.",
    ],
    [
        "PAYMENT RECEIPT", "Receipt No: RC-77", "Date: 20 March 2026", "",
        "Received with thanks from Acme Traders Pvt Ltd",
        "the sum of INR 5900.00 towards invoice INV-1001",
        "Mode of payment: UPI", "Authorised signatory",
    ],
    [
        "PURCHASE ORDER", "PO Number: PO-5521", "Date: 25 March 2026", "",
        "Vendor: Sunrise Hardware, Chennai",
        "Please supply 500 hex nuts and 200 washers.",
        "Delivery within 14 days. Ship to: Acme Traders Pvt Ltd, Pune",
    ],
]


# ---- tiny dependency-free PDF writer -------------------------------------


def build_pdf(pages: list[list[str]]) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_id = 3 + n * 2
    for i, lines in enumerate(pages):
        content_id = 4 + i * 2
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        text = ["BT", "/F1 14 Tf", "18 TL", "50 780 Td"]
        for line in lines:
            text.append(f"({esc(line)}) Tj T*")
        text.append("ET")
        stream = "\n".join(text).encode()
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# ---- harness --------------------------------------------------------------


def load_key() -> str:
    key = os.environ.get("SARVAM_API_KEY")
    env_file = HERE / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("SARVAM_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    if not key:
        sys.exit("SARVAM_API_KEY not set (env or .env)")
    return key


def make_server(key: str, base_path: Path) -> FastMCP:
    os.environ["SARVAM_API_KEY"] = key
    from sarvam_mcp.auth import StaticKeyProvider, set_auth

    set_auth(StaticKeyProvider(key))
    config = Config.load()

    @asynccontextmanager
    async def lifespan(_server: FastMCP):
        client = SarvamClient(config.base_url)
        try:
            yield ServerContext(
                config=config, client=client, audio_sink=build_sink("files", base_path)
            )
        finally:
            await client.aclose()

    server = FastMCP("doc-ai-smoke", lifespan=lifespan)
    vision.register(server)
    return server


class Check:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, float, str]] = []

    async def run(self, name: str, fn: Callable[[], Awaitable[str]]) -> None:
        t0 = time.monotonic()
        try:
            note = await fn()
            ok = True
        except AssertionError as exc:
            ok, note = False, f"ASSERT: {exc}"
        except Exception as exc:  # noqa: BLE001
            ok, note = False, f"{type(exc).__name__}: {str(exc)[:300]}"
            traceback.print_exc(file=sys.stderr)
        dt = time.monotonic() - t0
        self.rows.append((name, ok, dt, note))
        print(f"{'PASS' if ok else 'FAIL'}  {name:<34} {dt:6.1f}s  {note}", flush=True)


def save(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma list of: parse,classify,split,errors")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}

    def want(group: str) -> bool:
        return not only or group in only

    key = load_key()
    work = Path(tempfile.mkdtemp(prefix="doc-ai-smoke-"))
    bundle = work / "bundle.pdf"
    bundle.write_bytes(build_pdf(PAGES))
    invoice = work / "invoice.pdf"
    invoice.write_bytes(build_pdf(PAGES[:1]))
    server = make_server(key, work)
    chk = Check()

    async with Client(server) as client:

        async def tool(name: str, **kw: Any) -> dict[str, Any]:
            res = await client.call_tool(name, kw)
            return res.data

        def seg_types(result: dict[str, Any]) -> list[Any]:
            return [s.get("type") or (s.get("classification") or {}).get("type")
                    for s in result.get("segments", [])]

        # ---------- classify ----------
        if want("classify"):

            async def classify_single() -> str:
                out = await tool("sarvam_tools_vision_classify",
                                 document_path=str(invoice), categories=CATEGORIES)
                save("classify_single_invoice", out)
                assert out["status"] == "completed", out["status"]
                r = out["result"]
                assert r, "empty result"
                label = json.dumps(r)
                assert "invoice" in label.lower(), f"no 'invoice' in {label[:200]}"
                return f"review_required={out['review_required']} result_keys={sorted(r)}"

            async def classify_suggest() -> str:
                out = await tool("sarvam_tools_vision_classify", document_path=str(invoice))
                save("classify_no_categories", out)
                assert out["status"] == "completed"
                suggested = ((out["result"] or {}).get("suggested_type") or {}).get("name")
                assert suggested and "invoice" in suggested.lower(), f"suggested_type={suggested!r}"
                return f"suggested_type={suggested!r}"

            async def classify_other() -> str:
                out = await tool(
                    "sarvam_tools_vision_classify", document_path=str(invoice),
                    categories=[{"type": "passport", "description": "A government travel document"}],
                    unmatched_behavior="other",
                )
                save("classify_unmatched_other", out)
                assert out["status"] == "completed"
                got = (out["result"] or {}).get("type")
                assert got == "other", f"expected type 'other', got {got!r}"
                return f"type={got!r} review_required={out['review_required']}"

            async def classify_bundle_doc() -> str:
                out = await tool("sarvam_tools_vision_classify",
                                 document_path=str(bundle), categories=CATEGORIES)
                save("classify_bundle_document_scope", out)
                assert out["status"] == "completed"
                st = (out["result"] or {}).get("classification_status")
                assert st == "mixed", f"expected mixed for a multi-doc bundle, got {st!r}"
                return f"classification_status={st}"

            async def classify_bundle_pages() -> str:
                out = await tool("sarvam_tools_vision_classify", document_path=str(bundle),
                                 categories=CATEGORIES, scope="page", include_details=True)
                save("classify_bundle_page_scope", out)
                assert out["status"] == "completed"
                blob = json.dumps(out["result"]).lower()
                for t in ("invoice", "receipt", "purchase_order"):
                    assert t in blob, f"{t} missing from per-page result"
                return f"result_keys={sorted(out['result'])}"

            async def classify_png() -> str:
                if not shutil.which("pdftoppm"):
                    return "SKIPPED (pdftoppm not installed)"
                prefix = work / "page"
                subprocess.run(["pdftoppm", "-png", "-r", "100", "-f", "3", "-l", "3",
                                str(bundle), str(prefix)], check=True)
                png = next(work.glob("page*.png"))
                b64 = base64.b64encode(png.read_bytes()).decode()
                out = await tool("sarvam_tools_vision_classify", document_base64=b64,
                                 filename="receipt.png", categories=CATEGORIES)
                save("classify_png_base64", out)
                assert "receipt" in json.dumps(out["result"]).lower(), out["result"]
                return "png via base64 → receipt"

            await chk.run("classify: single invoice", classify_single)
            await chk.run("classify: no categories (suggest)", classify_suggest)
            await chk.run("classify: unmatched=other", classify_other)
            await chk.run("classify: bundle → mixed", classify_bundle_doc)
            await chk.run("classify: scope=page + details", classify_bundle_pages)
            await chk.run("classify: PNG via base64", classify_png)

        # ---------- split ----------
        if want("split"):

            async def split_semantic() -> str:
                out = await tool("sarvam_tools_vision_split", document_path=str(bundle),
                                 categories=CATEGORIES)
                save("split_semantic_with_categories", out)
                assert out["status"] == "completed"
                segs = out["result"]["segments"]
                pages = [s.get("pages") or s.get("page_range") for s in segs]
                assert len(segs) == 3, f"expected 3 segments, got {len(segs)}: {pages}"
                assert all("document_ref" in s for s in segs), "missing document_ref"
                return f"segments={len(segs)} pages={pages} types={seg_types(out['result'])}"

            async def split_fixed() -> str:
                out = await tool("sarvam_tools_vision_split", document_path=str(bundle),
                                 method="fixed_pages", pages_per_segment=2)
                save("split_fixed_pages", out)
                assert out["status"] == "completed"
                n = len(out["result"]["segments"])
                assert n == 2, f"expected 2 segments, got {n}"
                return f"segments={n}"

            async def split_ranges() -> str:
                out = await tool("sarvam_tools_vision_split", document_path=str(bundle),
                                 method="page_ranges",
                                 segment_ranges=[{"start": 1, "end": 2}, {"start": 3, "end": 3},
                                                 {"start": 4, "end": 4}])
                save("split_page_ranges", out)
                assert out["status"] == "completed"
                n = len(out["result"]["segments"])
                assert n == 3, f"expected 3 segments, got {n}"
                return f"segments={n}"

            async def split_triggers() -> str:
                starts = "^(TAX INVOICE|PAYMENT RECEIPT|PURCHASE ORDER)"
                out = await tool(
                    "sarvam_tools_vision_split", document_path=str(bundle), method="triggers",
                    split_on=[{"type": "text", "match": {"regex": starts}}],
                )
                save("split_triggers_text", out)
                assert out["status"] == "completed"
                n = len(out["result"]["segments"])
                assert n == 3, f"expected 3 segments, got {n}"
                return f"segments={n}"

            async def split_details() -> str:
                out = await tool("sarvam_tools_vision_split", document_path=str(bundle),
                                 method="fixed_pages", pages_per_segment=4, include_details=True)
                save("split_include_details", out)
                assert out["status"] == "completed"
                plain = json.dumps(out["result"])
                return f"result_bytes={len(plain)} raw_keys={sorted(out['raw'])}"

            await chk.run("split: semantic + categories", split_semantic)
            await chk.run("split: fixed_pages=2", split_fixed)
            await chk.run("split: page_ranges", split_ranges)
            await chk.run("split: triggers (text regex)", split_triggers)
            await chk.run("split: include_details", split_details)

        # ---------- parse (renamed from digitise) ----------
        if want("parse"):

            async def parse_md() -> str:
                out = await tool("sarvam_tools_vision_parse", document_path=str(invoice),
                                 output_format="md")
                save("parse_md", out)
                assert out["status"] == "completed", out["status"]
                url = (out["download"] or {}).get("download_urls") or out["download"]
                assert url, "no download info"
                first = json.dumps(url)
                return f"status=completed download={first[:120]}"

            async def job_status() -> str:
                out = await tool("sarvam_tools_vision_parse", document_path=str(invoice))
                st = await tool("sarvam_tools_vision_job_status", job_id=out["job_id"])
                save("job_status", st)
                assert st["status"] == "completed", st["status"]
                return f"job {st['job_id']} → {st['status']}"

            await chk.run("parse: invoice → md (new /parse path)", parse_md)
            await chk.run("job_status after parse", job_status)

        # ---------- error handling ----------
        if want("errors"):

            async def dup_categories() -> str:
                dup = [{"type": "invoice", "description": "a"}, {"type": "invoice", "description": "b"}]
                try:
                    await tool("sarvam_tools_vision_classify", document_path=str(invoice),
                               categories=dup)
                except Exception as exc:  # noqa: BLE001
                    return f"rejected as expected: {str(exc)[:140]}"
                raise AssertionError("duplicate category names were accepted")

            async def bad_ranges() -> str:
                try:
                    await tool("sarvam_tools_vision_split", document_path=str(bundle),
                               method="page_ranges",
                               segment_ranges=[{"start": 1, "end": 2}])  # does not cover all 4 pages
                except Exception as exc:  # noqa: BLE001
                    return f"rejected as expected: {str(exc)[:140]}"
                raise AssertionError("incomplete page_ranges were accepted")

            async def unknown_job() -> str:
                try:
                    await tool("sarvam_tools_vision_job_status", job_id="does-not-exist")
                except Exception as exc:  # noqa: BLE001
                    return f"rejected as expected: {str(exc)[:140]}"
                raise AssertionError("unknown job id returned success")

            async def bad_key() -> str:
                from sarvam_mcp.auth import StaticKeyProvider, set_auth

                set_auth(StaticKeyProvider("sk_definitely_invalid_key"))
                try:
                    await tool("sarvam_tools_vision_classify", document_path=str(invoice))
                except Exception as exc:  # noqa: BLE001
                    return f"rejected as expected: {str(exc)[:140]}"
                finally:
                    set_auth(StaticKeyProvider(key))
                raise AssertionError("invalid API key was accepted")

            await chk.run("errors: duplicate category names", dup_categories)
            await chk.run("errors: page_ranges not covering doc", bad_ranges)
            await chk.run("errors: unknown job id", unknown_job)
            await chk.run("errors: invalid API key", bad_key)

    shutil.rmtree(work, ignore_errors=True)
    failed = [r for r in chk.rows if not r[1]]
    print(f"\n{len(chk.rows) - len(failed)}/{len(chk.rows)} passed")
    save("_summary", [{"name": n, "ok": ok, "seconds": round(s, 1), "note": note}
                      for n, ok, s, note in chk.rows])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
