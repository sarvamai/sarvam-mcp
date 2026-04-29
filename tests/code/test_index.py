"""Docs chunking + keyword search."""

from __future__ import annotations

from sarvam_mcp.code.index import chunk_docs, search

SAMPLE_DOCS = """# Sarvam APIs

Welcome to the Sarvam developer docs.

## Speech-to-Text

Use `saaras:v3` to transcribe audio in 23 Indic languages.

## Text-to-Speech

TTS (bulbul:v3) is the current model with 38 speakers.

### Streaming TTS

Send a WebSocket request to the streaming endpoint for low-latency synthesis.

## Translation

Mayura v1 covers 11 languages with formal and colloquial modes.
"""


def test_chunks_split_on_headings():
    chunks = chunk_docs(SAMPLE_DOCS)
    titles = [c.heading for c in chunks]
    assert "Sarvam APIs" in titles
    assert "Speech-to-Text" in titles
    assert "Streaming TTS" in titles


def test_search_ranks_heading_matches_high():
    chunks = chunk_docs(SAMPLE_DOCS)
    hits = search(chunks, "streaming TTS", limit=3)
    assert hits, "expected at least one hit"
    assert hits[0].chunk.heading == "Streaming TTS"


def test_search_returns_empty_for_no_match():
    chunks = chunk_docs(SAMPLE_DOCS)
    hits = search(chunks, "kubernetes deployment yaml", limit=5)
    assert hits == []


def test_chunk_anchors_are_url_safe():
    chunks = chunk_docs(SAMPLE_DOCS)
    for c in chunks:
        # No whitespace, no leading/trailing dashes.
        assert " " not in c.anchor
        assert not c.anchor.startswith("-")
        assert not c.anchor.endswith("-")
