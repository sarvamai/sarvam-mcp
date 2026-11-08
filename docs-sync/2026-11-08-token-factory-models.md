# Docs sync — 2026-11-08 (Token Factory models)

Source: sarvamai/sarvam-fern-config@9311936cfd2211d6ff75b95fdeb4c4e51bfad9e1

## What changed in the docs

1. Three new Provisioned Throughput models: `qwen38-27b` (/v2/chat/completions, /v2/responses),
   `clef` (/v2/systemone, Decisions API), `embeddinggemma-2` (/v2/embeddings).
2. Chat Completions return one completion per request on every model: `n > 1` now returns
   `400 invalid_request_error` on both /v1 and /v2.
3. Price cuts: `deepseekv4.1-flash-1017` to Rs 14 / Rs 0.55, new `deepseekv4.1-flash-1017-interactive`;
   `kimi-k3.1-pro` to Rs 200 / Rs 950.

## What this repo needs

- `src/sarvam_mcp/code/_data.py`: add the three model IDs to the /v2 model enumeration and the
  PRICING map; change the `n` description to "must be 1".
- `src/sarvam_mcp/tools/llm.py`: constrain `n` to 1 so callers get a local validation error
  instead of a 400 from the API.
- Consider new tools for `/v2/embeddings` and `/v2/systemone`, which the MCP server does not expose.
