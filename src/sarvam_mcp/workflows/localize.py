"""``sv_localize`` — translate string-table files into Indic languages.

Reads a source i18n file (JSON or simple `key=value` text), translates the
string values via Sarvam-Translate, and writes a localized variant beside
the source. Picks Sarvam-Translate v1 by default for the wider 22-language
coverage; use Mayura via the `model` arg if you need colloquial mode.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import LanguageCode, ready_ctx
from sarvam_mcp.workflows._helpers import translate_text

# Cap protects against runaway translation cost on a misuse.
MAX_STRINGS = 500


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_localize",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Translate a JSON or `key=value` string-table file into another "
            "language. Walks all string values (nested JSON supported), runs "
            "each through Sarvam-Translate, and writes a sibling file with "
            "the language code as suffix (e.g. `messages.en.json` → "
            "`messages.hi.json`).\n\n"
            "For repos with many files, call this tool once per locale file. "
            "Skips non-string leaves (numbers, booleans, etc.) untouched."
        ),
    )
    async def sv_localize(
        ctx: Context,
        source_path: str = Field(
            description="Absolute path to a JSON file or `key=value` text file.",
        ),
        target_language_code: LanguageCode = Field(
            description="Language to translate strings into.",
        ),
        source_language_code: LanguageCode = Field(
            default="en-IN",
            description="Language of the source strings.",
        ),
        output_path: str | None = Field(
            default=None,
            description=(
                "Where to write the localized file. Defaults to the source path "
                "with the target language code injected before the extension."
            ),
        ),
        model: str = Field(
            default="sarvam-translate:v1",
            description="`sarvam-translate:v1` (22 langs) or `mayura:v1`.",
        ),
        max_strings: int = Field(
            default=MAX_STRINGS,
            ge=1,
            le=2000,
            description="Hard cap on values translated per call.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        src = Path(source_path).expanduser()
        if not src.is_file():
            raise FileNotFoundError(f"Source file not found: {src}")

        out_path = (
            Path(output_path).expanduser()
            if output_path
            else _default_output_path(src, target_language_code)
        )

        with measure_tool() as metrics:
            if src.suffix.lower() == ".json":
                raw_json = await asyncio.to_thread(src.read_text)
                data = json.loads(raw_json)
                strings: list[tuple[list[str | int], str]] = []
                _collect_strings(data, [], strings)
                if len(strings) > max_strings:
                    raise ValueError(
                        f"File has {len(strings)} strings; max_strings={max_strings}. "
                        "Raise the cap or split the file."
                    )

                await ctx.info(f"Translating {len(strings)} strings…")
                for i, (path_parts, value) in enumerate(strings):
                    translated = await translate_text(
                        sc,
                        value,
                        source_language_code=source_language_code,
                        target_language_code=target_language_code,
                        model=model,
                        metrics=metrics,
                    )
                    _set_path(data, path_parts, translated)
                    if (i + 1) % 25 == 0:
                        await ctx.report_progress(i + 1, len(strings))

                await asyncio.to_thread(
                    out_path.write_text,
                    json.dumps(data, indent=2, ensure_ascii=False),
                )
                count = len(strings)
            else:
                # Treat as `key=value` lines, preserving comments + blank lines.
                raw_text = await asyncio.to_thread(src.read_text)
                lines = raw_text.splitlines()
                count = 0
                out_lines: list[str] = []
                for raw in lines:
                    if "=" not in raw or raw.lstrip().startswith("#"):
                        out_lines.append(raw)
                        continue
                    key, _, value = raw.partition("=")
                    value = value.strip()
                    if not value:
                        out_lines.append(raw)
                        continue
                    if count >= max_strings:
                        out_lines.append(raw)
                        continue
                    translated = await translate_text(
                        sc,
                        value,
                        source_language_code=source_language_code,
                        target_language_code=target_language_code,
                        model=model,
                        metrics=metrics,
                    )
                    out_lines.append(f"{key}= {translated}")
                    count += 1
                await asyncio.to_thread(out_path.write_text, "\n".join(out_lines) + "\n")

        return {
            "source_path": str(src),
            "output_path": str(out_path),
            "strings_translated": count,
            "source_language": source_language_code,
            "target_language": target_language_code,
            "model": model,
            "observability": metrics.to_response_block(),
        }


# ----- helpers -------------------------------------------------------------


def _default_output_path(src: Path, target: str) -> Path:
    """`messages.en.json` + 'hi-IN' → `messages.hi-IN.json`. Fall back to .out."""
    stem = src.stem
    parts = stem.split(".")
    if len(parts) >= 2:
        parts[-1] = target
        new_stem = ".".join(parts)
    else:
        new_stem = f"{stem}.{target}"
    return src.with_name(f"{new_stem}{src.suffix}")


def _collect_strings(
    node: Any, path: list[str | int], out: list[tuple[list[str | int], str]]
) -> None:
    """Walk a JSON tree and gather (path, string-value) pairs."""
    if isinstance(node, dict):
        for k, v in node.items():
            _collect_strings(v, [*path, k], out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _collect_strings(v, [*path, i], out)
    elif isinstance(node, str) and node.strip():
        out.append((path, node))


def _set_path(root: Any, path: list[str | int], value: str) -> None:
    cursor = root
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
