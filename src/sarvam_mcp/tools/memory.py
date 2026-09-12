"""Persistent agent memory tools backed by CogniCore.

Optional dependency — gated behind ``pip install "sarvam-mcp[memory]"``.
All cognicore imports are lazy (inside tool function bodies) so the module
loads fine even when cognicore-env is not installed.  Tools use
``server_ctx(ctx)`` — no Sarvam API key required.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.tools._common import server_ctx

logger = logging.getLogger("sarvam_mcp.tools.memory")

_INSTALL_HINT = (
    "cognicore-env is not installed. "
    'Run: pip install "sarvam-mcp[memory]"'
)


def _get_store(ctx: Context) -> Any:
    """Return the shared TFIDFMemoryBackend, creating it on first use.

    The store is cached on ``ServerContext.memory_store`` so every tool
    in this session shares the same instance (and the same in-memory index).
    """
    try:
        from cognicore.memory.tfidf_backend import TFIDFMemoryBackend
    except ImportError:
        return None

    sc = server_ctx(ctx)
    if sc.memory_store is None:
        db_path = str(Path(sc.config.cognicore_db_path).expanduser())
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        sc.memory_store = TFIDFMemoryBackend(persistence_path=db_path)
        logger.info("CogniCore memory initialised — persistence_path=%s", db_path)
    return sc.memory_store


def register(mcp: FastMCP) -> None:
    """Register the ``sarvam_memory_*`` tool namespace."""

    # ------------------------------------------------------------------ #
    # sarvam_memory_remember
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="sarvam_memory_remember",
        description=(
            "Memory tool — stores a fact, decision, or experience for later recall. "
            "No Sarvam API key needed.\n\n"
            "Store a memory with category, tags, and importance score. "
            "The memory persists across sessions in a local JSON file."
        ),
    )
    async def sarvam_memory_remember(
        ctx: Context,
        text: str = Field(
            description="The fact, decision, or experience to remember.",
        ),
        category: str = Field(
            default="general",
            description=(
                "Category for the memory (e.g. 'decision', 'failure', "
                "'preference', 'fact', 'procedure')."
            ),
        ),
        tags: str = Field(
            default="",
            description="Comma-separated tags for richer retrieval (e.g. 'translation,tamil,formal').",
        ),
        importance: int = Field(
            default=5,
            description="Importance score from 1 (trivial) to 10 (critical). Default 5.",
            ge=1,
            le=10,
        ),
    ) -> dict[str, Any]:
        store = _get_store(ctx)
        if store is None:
            return {"status": "error", "message": _INSTALL_HINT}

        try:
            from cognicore.memory.base import MemoryEntry
        except ImportError:
            return {"status": "error", "message": _INSTALL_HINT}

        metadata: dict[str, Any] = {"importance": importance}
        if tags:
            metadata["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

        entry = MemoryEntry(
            text=text,
            category=category,
            metadata=metadata,
        )
        entry_id = store.store(entry)
        store.save()

        return {
            "status": "stored",
            "entry_id": entry_id,
            "category": category,
            "importance": importance,
            "tags": metadata.get("tags", []),
            "message": f"Memory stored with ID {entry_id}.",
        }

    # ------------------------------------------------------------------ #
    # sarvam_memory_recall
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="sarvam_memory_recall",
        description=(
            "Memory tool — retrieves relevant memories using TF-IDF cosine similarity. "
            "No Sarvam API key needed.\n\n"
            "Search stored memories by keyword query. Returns the top-k most "
            "relevant results, optionally filtered by category."
        ),
    )
    async def sarvam_memory_recall(
        ctx: Context,
        query: str = Field(
            description="Search query — keywords describing what you are looking for.",
        ),
        top_k: int = Field(
            default=5,
            description="Maximum number of results to return.",
            ge=1,
            le=50,
        ),
        category: str | None = Field(
            default=None,
            description="Optional category filter (e.g. 'decision', 'failure').",
        ),
    ) -> dict[str, Any]:
        store = _get_store(ctx)
        if store is None:
            return {"status": "error", "message": _INSTALL_HINT}

        results = store.search(query, top_k=top_k, category=category)

        memories = []
        for r in results:
            entry = r.entry if hasattr(r, "entry") else r
            mem: dict[str, Any] = {
                "text": entry.text if hasattr(entry, "text") else str(entry),
                "category": getattr(entry, "category", "general"),
                "score": round(r.score, 4) if hasattr(r, "score") else None,
            }
            if hasattr(entry, "metadata") and entry.metadata:
                mem["importance"] = entry.metadata.get("importance")
                mem["tags"] = entry.metadata.get("tags", [])
            if hasattr(entry, "entry_id"):
                mem["entry_id"] = entry.entry_id
            memories.append(mem)

        return {
            "status": "ok",
            "query": query,
            "count": len(memories),
            "memories": memories,
        }

    # ------------------------------------------------------------------ #
    # sarvam_memory_reflect
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="sarvam_memory_reflect",
        description=(
            "Memory tool — analyzes patterns across stored memories. "
            "No Sarvam API key needed.\n\n"
            "Performs local pattern analysis: identifies recurring failure "
            "categories, successful patterns, and knowledge gaps. "
            "Does NOT call an LLM — pure local computation."
        ),
    )
    async def sarvam_memory_reflect(
        ctx: Context,
    ) -> dict[str, Any]:
        store = _get_store(ctx)
        if store is None:
            return {"status": "error", "message": _INSTALL_HINT}

        entries = store.entries if isinstance(store.entries, list) else list(store.entries)
        total = len(entries)
        if total == 0:
            return {
                "status": "ok",
                "total_memories": 0,
                "message": "No memories stored yet. Use sarvam_memory_remember to start building your memory.",
            }

        # Category breakdown
        cat_counts: Counter[str] = Counter()
        failure_texts: list[str] = []
        success_texts: list[str] = []
        importance_sum = 0.0
        importance_count = 0

        for e in entries:
            cat = getattr(e, "category", "general")
            cat_counts[cat] += 1
            meta = getattr(e, "metadata", {}) or {}
            imp = meta.get("importance")
            if imp is not None:
                importance_sum += imp
                importance_count += 1
            if cat == "failure":
                failure_texts.append(getattr(e, "text", ""))
            elif cat in ("procedure", "decision"):
                success_texts.append(getattr(e, "text", ""))

        avg_importance = round(importance_sum / importance_count, 1) if importance_count else None

        # Identify recurring keywords in failures
        failure_keywords: Counter[str] = Counter()
        for text in failure_texts:
            words = set(text.lower().split())
            # Filter very short/common words
            for w in words:
                if len(w) > 3:
                    failure_keywords[w] += 1

        return {
            "status": "ok",
            "total_memories": total,
            "category_breakdown": dict(cat_counts.most_common()),
            "average_importance": avg_importance,
            "failure_count": len(failure_texts),
            "success_count": len(success_texts),
            "recurring_failure_keywords": dict(failure_keywords.most_common(10)),
            "insights": _build_insights(cat_counts, failure_texts, success_texts, total),
        }

    # ------------------------------------------------------------------ #
    # sarvam_memory_forget
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="sarvam_memory_forget",
        description=(
            "Memory tool — deletes a memory by its entry ID. "
            "No Sarvam API key needed.\n\n"
            "Permanently removes a memory from the store. "
            "Use sarvam_memory_list or sarvam_memory_recall to find entry IDs."
        ),
    )
    async def sarvam_memory_forget(
        ctx: Context,
        entry_id: str = Field(
            description="The entry ID of the memory to delete (e.g. 'mem_1726149600000_3').",
        ),
    ) -> dict[str, Any]:
        store = _get_store(ctx)
        if store is None:
            return {"status": "error", "message": _INSTALL_HINT}

        # TFIDFMemoryBackend stores entries as a list; find by entry_id
        original_count = len(store.entries)
        store.entries = [
            e for e in store.entries
            if getattr(e, "entry_id", None) != entry_id
        ]
        removed = original_count - len(store.entries)

        if removed == 0:
            return {
                "status": "not_found",
                "message": f"No memory found with entry_id '{entry_id}'.",
            }

        store.save()
        return {
            "status": "deleted",
            "entry_id": entry_id,
            "message": f"Memory '{entry_id}' deleted.",
        }

    # ------------------------------------------------------------------ #
    # sarvam_memory_list
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="sarvam_memory_list",
        description=(
            "Memory tool — lists recent memories. "
            "No Sarvam API key needed.\n\n"
            "Returns stored memories, optionally filtered by category. "
            "Most recent memories are returned first."
        ),
    )
    async def sarvam_memory_list(
        ctx: Context,
        category: str | None = Field(
            default=None,
            description="Optional category filter.",
        ),
        limit: int = Field(
            default=20,
            description="Maximum number of memories to return.",
            ge=1,
            le=100,
        ),
    ) -> dict[str, Any]:
        store = _get_store(ctx)
        if store is None:
            return {"status": "error", "message": _INSTALL_HINT}

        entries = store.entries if isinstance(store.entries, list) else list(store.entries)

        if category:
            entries = [e for e in entries if getattr(e, "category", "general") == category]

        # Most recent first (entries are appended, so reverse)
        recent = list(reversed(entries[-limit:]))

        memories = []
        for e in recent:
            meta = getattr(e, "metadata", {}) or {}
            mem: dict[str, Any] = {
                "text": getattr(e, "text", ""),
                "category": getattr(e, "category", "general"),
            }
            if hasattr(e, "entry_id") and e.entry_id:
                mem["entry_id"] = e.entry_id
            if "importance" in meta:
                mem["importance"] = meta["importance"]
            if "tags" in meta:
                mem["tags"] = meta["tags"]
            memories.append(mem)

        return {
            "status": "ok",
            "count": len(memories),
            "total_in_store": len(store.entries) if isinstance(store.entries, list) else 0,
            "category_filter": category,
            "memories": memories,
        }

    # ------------------------------------------------------------------ #
    # sarvam_memory_stats
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="sarvam_memory_stats",
        description=(
            "Memory tool — shows memory store statistics. "
            "No Sarvam API key needed.\n\n"
            "Returns total memory count, category breakdown, and persistence path."
        ),
    )
    async def sarvam_memory_stats(
        ctx: Context,
    ) -> dict[str, Any]:
        store = _get_store(ctx)
        if store is None:
            return {"status": "error", "message": _INSTALL_HINT}

        entries = store.entries if isinstance(store.entries, list) else list(store.entries)
        total = len(entries)

        cat_counts: Counter[str] = Counter()
        for e in entries:
            cat_counts[getattr(e, "category", "general")] += 1

        sc = server_ctx(ctx)
        db_path = str(Path(sc.config.cognicore_db_path).expanduser())

        return {
            "status": "ok",
            "total_memories": total,
            "category_breakdown": dict(cat_counts.most_common()),
            "persistence_path": db_path,
            "backend": "TFIDFMemoryBackend",
        }


def _build_insights(
    cat_counts: Counter[str],
    failure_texts: list[str],
    success_texts: list[str],
    total: int,
) -> list[str]:
    """Generate simple textual insights from memory patterns."""
    insights: list[str] = []

    if failure_texts:
        pct = round(len(failure_texts) / total * 100)
        insights.append(
            f"{len(failure_texts)} failure memories ({pct}% of total) — "
            "consider reviewing recurring failure patterns."
        )

    if success_texts:
        insights.append(
            f"{len(success_texts)} procedural/decision memories — "
            "these represent reusable successful approaches."
        )

    top_cats = cat_counts.most_common(3)
    if top_cats:
        summary = ", ".join(f"{cat} ({n})" for cat, n in top_cats)
        insights.append(f"Top categories: {summary}.")

    if not failure_texts and total > 0:
        insights.append("No failures recorded — consider logging failed approaches for future reference.")

    return insights
