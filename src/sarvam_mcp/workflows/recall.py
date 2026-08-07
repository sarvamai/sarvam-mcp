"""``sv_recall`` — Q&A across a mixed collection of Indic docs + audio files.

Index step is in-memory (per call): every audio file is transcribed, every
text/markdown file is read, and the concatenation is fed to the LLM as
grounded context. For larger corpora this should be promoted to a real
vector store; the v1 contract is intentionally tiny and stateless.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, SarvamLLM, ready_ctx
from sarvam_mcp.workflows._helpers import llm_complete, stt_transcribe

AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"}
TEXT_EXTS = {".txt", ".md", ".markdown", ".rst", ".log", ".json", ".yaml", ".yml"}

# Hard cap on the chunk we feed into the LLM. Cheap protection against
# blowing context window or running up cost.
MAX_CHARS = 24_000


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_recall",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Answer a natural-language question grounded in a set of files. "
            "Audio files are transcribed; text/markdown files "
            "are read directly. Everything is concatenated (capped at "
            f"{MAX_CHARS} chars) and passed to the LLM with a grounded-QA "
            "system prompt. Useful for quickly querying meeting recordings, "
            "Indic-language notes, or mixed-format research folders."
        ),
    )
    async def sv_recall(
        ctx: Context,
        question: str = Field(description="The question to answer."),
        paths: list[str] = Field(
            description=(
                "Absolute paths to files (audio or text) and/or directories. "
                "Directories are walked recursively."
            ),
        ),
        stt_language: LanguageCode = Field(
            default="unknown",
            description="STT hint applied to every audio file.",
        ),
        max_files: int = Field(default=20, ge=1, le=100),
        llm_model: SarvamLLM = Field(
            default="sarvam-105b",
            description="`sarvam-105b` (flagship, the only current chat model).",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        files = _gather_files(paths, max_files)
        if not files:
            return {
                "answer": "No supported files found at the given paths.",
                "sources": [],
                "observability": {},
            }

        sources: list[dict[str, Any]] = []
        with measure_tool() as metrics:
            chunks: list[str] = []
            running = 0
            for file_path in files:
                if running >= MAX_CHARS:
                    sources.append({"path": str(file_path), "skipped": "max chars reached"})
                    continue
                if file_path.suffix.lower() in AUDIO_EXTS:
                    await ctx.info(f"Transcribing {file_path.name}…")
                    transcript, detected = await stt_transcribe(
                        sc, file_path, language_code=stt_language, metrics=metrics
                    )
                    text = transcript or ""
                    sources.append(
                        {
                            "path": str(file_path),
                            "kind": "audio",
                            "language_code": detected,
                            "chars": len(text),
                        }
                    )
                else:
                    try:
                        text = file_path.read_text(errors="ignore")
                    except Exception as exc:  # noqa: BLE001
                        sources.append({"path": str(file_path), "error": repr(exc)})
                        continue
                    sources.append(
                        {"path": str(file_path), "kind": "text", "chars": len(text)}
                    )

                if not text.strip():
                    continue
                room = MAX_CHARS - running
                snippet = text if len(text) <= room else text[:room]
                chunks.append(f"--- FILE: {file_path.name} ---\n{snippet}\n")
                running += len(snippet)

            await ctx.info(
                f"Querying the LLM with {running} chars from {len(chunks)} sources…"
            )
            corpus = "\n".join(chunks) if chunks else "(no content available)"
            answer = await llm_complete(
                sc,
                [
                    {
                        "role": "system",
                        "content": (
                            "You answer questions strictly using the provided file "
                            "contents. If the answer is not present, say so. Cite "
                            "the source file name(s) at the end of your answer."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"FILES:\n{corpus}\n\nQUESTION:\n{question}"
                        ),
                    },
                ],
                model=llm_model,
                temperature=0.2,
                max_tokens=800,
                metrics=metrics,
            )

        return {
            "answer": answer,
            "sources": sources,
            "files_indexed": len(sources),
            "chars_used": running,
            "observability": metrics.to_response_block(),
        }


def _gather_files(paths: list[str], max_files: int) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_file():
            if _supported(p):
                out.append(p)
        elif p.is_dir():
            for sub in sorted(p.rglob("*")):
                if sub.is_file() and _supported(sub):
                    out.append(sub)
                if len(out) >= max_files:
                    break
        if len(out) >= max_files:
            break
    return out[:max_files]


def _supported(p: Path) -> bool:
    s = p.suffix.lower()
    return s in AUDIO_EXTS or s in TEXT_EXTS
