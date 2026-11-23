"""Embeddings — ``POST /v2/embeddings`` (EmbeddingGemma 2, Provisioned Throughput).

OpenAI-compatible. One 768-dimension, unit-length float vector per input, in
input order. Only orgs Sarvam has enabled can call it (others get 404/400).
``dimensions`` is not supported (400); ``encoding_format`` is ``float`` or
``base64`` only. The API does NOT add task prefixes — EmbeddingGemma 2 is
trained with them, so pass ``task`` to prepend the documented one.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.http.errors import SarvamAPIError
from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._chat_models import provisioned_access_error
from sarvam_mcp.tools._common import ready_ctx

EMBEDDINGS_PATH = "/v2/embeddings"
EMBEDDING_MODEL = "embeddinggemma-2"

EmbeddingTask = Literal[
    "query",
    "document",
    "question_answering",
    "fact_checking",
    "classification",
    "clustering",
    "similarity",
    "code_retrieval",
]
# Prefixes from docs.sarvam.ai/api/token-factory/models/embeddinggemma-2 ("Task prefixes").
TASK_PREFIXES: dict[str, str] = {
    "query": "task: search result | query: ",
    "document": "title: none | text: ",
    "question_answering": "task: question answering | query: ",
    "fact_checking": "task: fact checking | query: ",
    "classification": "task: classification | query: ",
    "clustering": "task: clustering | query: ",
    "similarity": "task: sentence similarity | query: ",
    "code_retrieval": "task: code retrieval | query: ",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_embed",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Embed text with EmbeddingGemma 2 (POST /v2/embeddings). PROVISIONED THROUGHPUT: enabled "
            "per organisation — contact Sarvam support (support@sarvam.ai) with your expected "
            "volume to get access; without it the call returns 404. Returns one 768-dim "
            "unit-length vector per input, in order. Each string may be up to 8,192 tokens. "
            "Pass `task` to prepend the documented "
            "task prefix (e.g. 'query' for search queries, 'document' for passages to index) — "
            "without a prefix retrieval quality drops. Vectors are large, so by default they are "
            "written to a JSON file under SARVAM_MCP_BASE_PATH and only a short preview is returned; "
            "set return_vectors=true to get them inline. Billed ₹2 per 1M input tokens."
        ),
    )
    async def sarvam_embed(
        ctx: Context,
        input: str | list[str] = Field(
            description="A string or a non-empty list of strings (each up to 8,192 tokens).",
        ),
        task: EmbeddingTask | None = Field(
            default=None,
            description=(
                "Prepend the documented task prefix to every string: query | document | "
                "question_answering | fact_checking | classification | clustering | similarity | "
                "code_retrieval. Omit if your strings already carry a prefix."
            ),
        ),
        encoding_format: Literal["float", "base64"] = Field(
            default="float",
            description=(
                "'float' (default) or 'base64' (768 little-endian float32 values). "
                "Anything else is a 400."
            ),
        ),
        return_vectors: bool = Field(
            default=False,
            description="Return the vectors inline instead of writing them to a file.",
        ),
    ) -> dict[str, Any]:
        sc = await ready_ctx(ctx)
        texts = [input] if isinstance(input, str) else list(input)
        if not texts:
            raise ValueError("input must contain at least one string.")
        if task:
            prefix = TASK_PREFIXES[task]
            texts = [prefix + t for t in texts]

        with measure_tool() as metrics:
            try:
                payload, call = await sc.client.post_json(
                    EMBEDDINGS_PATH,
                    json_body={
                        "model": EMBEDDING_MODEL,
                        "input": texts,
                        "encoding_format": encoding_format,
                    },
                )
            except SarvamAPIError as exc:
                better = provisioned_access_error(exc, EMBEDDING_MODEL)
                if better is not None:
                    raise better from exc
                raise
            metrics.merge(call)

        body = payload if isinstance(payload, dict) else {}
        items = sorted(body.get("data") or [], key=lambda d: d.get("index", 0))
        vectors = [d.get("embedding") for d in items]
        dims = len(vectors[0]) if vectors and isinstance(vectors[0], list) else None
        result: dict[str, Any] = {
            "model": body.get("model", EMBEDDING_MODEL),
            "count": len(vectors),
            "dimensions": dims,
            "encoding_format": encoding_format,
            "usage": body.get("usage"),
            "observability": metrics.to_response_block(),
        }
        if return_vectors:
            result["embeddings"] = vectors
            return result

        out_dir = Path(sc.config.base_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"sarvam-embeddings-{uuid.uuid4().hex[:8]}.json"
        out_path.write_text(json.dumps({"model": result["model"], "embeddings": vectors}))
        result["file_path"] = str(out_path)
        result["preview"] = [v[:5] if isinstance(v, list) else str(v)[:24] for v in vectors[:3]]
        return result
