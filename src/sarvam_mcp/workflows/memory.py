"""Persistent cross-session memory for sarvam-mcp.

Stores and retrieves named memory entries backed by a local JSON Lines file
at ``~/.sarvam/memory.jsonl``.

File locking: uses ``fcntl.flock`` on Unix/macOS for safe concurrent access.
On Windows locking is skipped — concurrent writes from multiple processes may
corrupt the file (a known caveat; single-process usage is safe).
"""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

_STORE_PATH = Path("~/.sarvam/memory.jsonl").expanduser()


# ---------------------------------------------------------------------------
# File locking — Unix only
# ---------------------------------------------------------------------------

if sys.platform != "win32":
    import fcntl as _fcntl

    def _lock(fh: Any) -> None:
        _fcntl.flock(fh, _fcntl.LOCK_EX)

    def _unlock(fh: Any) -> None:
        _fcntl.flock(fh, _fcntl.LOCK_UN)

else:  # pragma: no cover — Windows: locking is a no-op
    def _lock(fh: Any) -> None:  # type: ignore[misc]
        pass

    def _unlock(fh: Any) -> None:  # type: ignore[misc]
        pass


# ---------------------------------------------------------------------------
# Low-level I/O
# ---------------------------------------------------------------------------


def _load_entries() -> list[dict[str, Any]]:
    """Read all entries from the JSON Lines store (no lock required — reads are atomic)."""
    if not _STORE_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    with _STORE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                with contextlib.suppress(json.JSONDecodeError):
                    out.append(json.loads(stripped))
    return out


def _save_entries(entries: list[dict[str, Any]]) -> None:
    """Atomically overwrite the JSON Lines store via a temp-file rename."""
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    tmp.replace(_STORE_PATH)


def _locked_update(fn: Any) -> Any:
    """Acquire an exclusive lock, load entries, call ``fn(entries)``, persist result.

    ``fn`` must return ``(new_entries, return_value)``.
    """
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _STORE_PATH.with_suffix(".lock")
    with lock_path.open("a", encoding="utf-8") as lf:
        _lock(lf)
        try:
            entries = _load_entries()
            new_entries, value = fn(entries)
            _save_entries(new_entries)
            return value
        finally:
            _unlock(lf)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_memory_store",
        description=(
            "Save a named memory entry to persistent local storage (~/.sarvam/memory.jsonl). "
            "If an entry with the same key already exists it is overwritten. "
            "Use this to preserve findings, preferences, or context across sessions."
        ),
    )
    def memory_store(
        key: str = Field(description="Unique identifier for this memory entry."),
        content: str = Field(description="The content to remember."),
        tags: list[str] = Field(default=[], description="Optional labels to categorise the entry."),
        domain: str | None = Field(
            default=None, description="Optional domain / namespace (e.g. 'project-x')."
        ),
    ) -> dict[str, Any]:
        now = _now_iso()

        def _update(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            existing = next((e for e in entries if e.get("key") == key), None)
            original_ts = existing.get("timestamp", now) if existing else now
            updated = [e for e in entries if e.get("key") != key]
            updated.append(
                {
                    "key": key,
                    "content": content,
                    "tags": tags,
                    "domain": domain,
                    "timestamp": original_ts,
                    "updated_at": now,
                }
            )
            return updated, {"status": "stored", "key": key, "timestamp": now}

        return _locked_update(_update)

    @mcp.tool(
        name="sarvam_memory_retrieve",
        description=(
            "Search stored memory entries by relevance to a query. "
            "Scores each entry by counting query-word matches in key, content, and tags. "
            "Optionally filter by tags. Returns the top matches sorted by score then recency."
        ),
    )
    def memory_retrieve(
        query: str = Field(description="Natural-language query to search for."),
        limit: int = Field(default=5, ge=1, description="Maximum number of results to return."),
        tags: list[str] = Field(
            default=[],
            description="If provided, only return entries that carry all of these tags.",
        ),
    ) -> dict[str, Any]:
        entries = _load_entries()
        query_words = set(query.lower().split())

        def _score(entry: dict[str, Any]) -> int:
            haystack = " ".join(
                [
                    entry.get("key", ""),
                    entry.get("content", ""),
                    " ".join(entry.get("tags", [])),
                ]
            ).lower()
            return sum(1 for w in query_words if w in haystack)

        if tags:
            tag_set = {t.lower() for t in tags}
            entries = [
                e for e in entries if tag_set.issubset({t.lower() for t in e.get("tags", [])})
            ]

        scored = sorted(entries, key=lambda e: (_score(e), e.get("updated_at", "")), reverse=True)
        results = [
            {
                "key": e.get("key"),
                "content": e.get("content"),
                "tags": e.get("tags", []),
                "domain": e.get("domain"),
                "timestamp": e.get("timestamp"),
                "score": _score(e),
            }
            for e in scored[:limit]
        ]
        return {"results": results}

    @mcp.tool(
        name="sarvam_memory_list",
        description=(
            "List stored memory entries, most-recent first. "
            "Optionally filter by domain. Use this to browse what has been remembered."
        ),
    )
    def memory_list(
        domain: str | None = Field(default=None, description="If set, only return entries for this domain."),
        limit: int = Field(default=20, ge=1, description="Maximum number of entries to return."),
    ) -> dict[str, Any]:
        entries = _load_entries()
        if domain is not None:
            entries = [e for e in entries if e.get("domain") == domain]
        entries = sorted(entries, key=lambda e: e.get("updated_at", ""), reverse=True)
        return {"entries": entries[:limit], "total": len(entries)}

    @mcp.tool(
        name="sarvam_memory_forget",
        description=(
            "Remove a memory entry by its key. "
            "Returns 'forgotten' if the entry existed, 'not_found' otherwise."
        ),
    )
    def memory_forget(
        key: str = Field(description="The key of the memory entry to remove."),
    ) -> dict[str, Any]:
        def _update(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            updated = [e for e in entries if e.get("key") != key]
            status = "forgotten" if len(updated) < len(entries) else "not_found"
            return updated, {"status": status, "key": key}

        return _locked_update(_update)
