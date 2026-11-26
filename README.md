# sarvam-mcp

Official Sarvam MCP server. Exposes the Sarvam Model APIs — STT, TTS, Dictate, Instant Voice Cloning, Translate, Transliterate, Language ID, chat LLMs (Sarvam-105B plus open-weight Token Factory models via Chat V2), the Responses API, Document Intelligence, Document Translation, Dubbing, Prism Decisions and Pronunciation Dictionaries — as first-class MCP tools so any MCP-aware client (Claude Desktop, Claude Code, Cursor, Windsurf, Zed) can call Sarvam with zero boilerplate.

Cross-platform Python package: **macOS, Windows, and Linux** (Python 3.11+).

## Quickstart

### 1. Get your API key

Sign up or log in at **[dashboard.sarvam.ai/key-management](https://dashboard.sarvam.ai/key-management)** and copy your API key (`sk_...`).

### 2. Add to your MCP client

Paste this into your MCP config JSON:

```json
{
  "mcpServers": {
    "sarvam": {
      "command": "uvx",
      "args": ["sarvam-mcp"],
      "env": {
        "SARVAM_API_KEY": "sk_..."
      }
    }
  }
}
```

Replace `sk_...` with your actual API key.

If you've installed via `pip install sarvam-mcp`, you can use the console script directly:

```json
{
  "mcpServers": {
    "sarvam": {
      "command": "sarvam-mcp",
      "env": {
        "SARVAM_API_KEY": "sk_..."
      }
    }
  }
}
```

### 3. Config file locations

| Client | Config path |
|---|---|
| **Cursor** | `~/.cursor/mcp.json` (macOS/Linux) · `%USERPROFILE%\.cursor\mcp.json` (Windows) |
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) · `%APPDATA%\Claude\claude_desktop_config.json` (Windows) |
| **Claude Code** | `claude mcp add sarvam -- uvx sarvam-mcp` (then set `SARVAM_API_KEY` env var) |
| **Windsurf** | Cascade settings → MCP servers |
| **Zed** | `settings.json` → `context_servers` |

### Alternative: credentials file

Instead of setting `SARVAM_API_KEY` in the JSON config, you can store it in `~/.sarvam/credentials`:

```ini
api_key = sk_...
```

The server checks `SARVAM_API_KEY` env var first, then falls back to `~/.sarvam/credentials`.

## Install

```bash
# Option A: run directly (no install needed)
uvx sarvam-mcp

# Option B: install globally
pip install sarvam-mcp
```

## Tools

All defaults below reflect the latest non-deprecated models.

| Tool | What it does | Default model |
|---|---|---|
| `sarvam_stt_transcribe` | Audio file → transcript (5 modes, including English via `mode=translate`) | `saaras:v4` |
| `sarvam_stt_realtime` | Mono WAV → realtime transcript | `saaras:v4` |
| `sarvam_tts_speak` | Text → audio file | `bulbul:v3`, `bulbul:v4-flash` |
| `sarvam_tts_stream` | Text → streamed audio | `bulbul:v3`, `bulbul:v4-flash` |
| `sarvam_translate` | Cross-language text translate | `mayura:v1` |
| `sarvam_document_translate` | Whole document, layout preserved | — |
| `sarvam_transliterate` | Script conversion | — |
| `sarvam_identify_language` | Language + script detect | — |
| `sarvam_text_analytics` | Retired endpoint — kept only as a stub that raises | — |
| `sarvam_llm_complete` | Chat completions (v1 for Sarvam models; v2 for glm5.3, gemma4, deepseek, kimi, qwen) | `sarvam-105b` |
| `sarvam_chat_v2_complete` | Chat Completion V2 (`/v2/chat/completions`): logprobs, session affinity, image input, `extra_body`, per-model rules | `sarvam-105b` |
| `sarvam_responses_create` | Stateless Responses API (`/v2/responses`) | `sarvam-105b` |
| `sarvam_embed` | Text embeddings, `embeddinggemma-2` (`/v2/embeddings`, provisioned) with optional task prefixes | `embeddinggemma-2` |
| `sarvam_list_models` | Chat models available to your key (`/v2/models`) | — |
| `sarvam_dictate_clip` | Short clip → clean, styled text with vocabulary + derived output | `dictate-v1` |
| `sarvam_dictate_job_submit` / `_job_status` | Dictate recordings up to 1 hour (async) | `dictate-v1` |
| `sarvam_cloned_voice_create` / `_speak` / `_list` / `_get` / `_delete` | Instant Voice Cloning (beta) | — |
| `sarvam_cloned_voice_watermark_detect` | Check audio for Sarvam's watermark (free) | — |
| `sarvam_vision_parse` | Document AI Parse: OCR to Markdown, HTML, or JSON, with each page's text | Sarvam Vision |
| `sarvam_vision_extract` | Document AI Extract: schema fields with per-field confidence and sources | Sarvam Vision |
| `sarvam_vision_classify` | Document AI Classify: label a document against up to 20 categories | Sarvam Vision |
| `sarvam_vision_split` | Document AI Split: separate a bundle of pages into its documents | Sarvam Vision |
| `sarvam_vision_capabilities` | Live Document AI limits, formats and features for your account | — |
| `sarvam_vision_job_status` | Poll a Document AI job | — |
| `sarvam_prism_decide` | Calibrated yes/no, pick-one and ordered-scale decisions | `sarvam-prism` |
| `sarvam_dubbing_submit` | Official video/audio dubbing job | — |
| `sarvam_pronunciation_list` | List pronunciation dictionaries | — |
| `sarvam_pronunciation_get` | Get a pronunciation dictionary | — |
| `sarvam_pronunciation_create` | Create a pronunciation dictionary | — |
| `sarvam_pronunciation_update` | Add/overwrite entries (others unchanged) | — |
| `sarvam_pronunciation_delete` | Delete a pronunciation dictionary | — |

Build-time helpers (`sarvam_code_*`) include `sarvam_code_pricing` (INR per plan) and `sarvam_code_rate_limits` (per plan, per API). Voice Agents (deployments, campaigns, analytics) are **not** in this server — Sarvam hosts a separate Voice Agents MCP at `https://mcp.sarvam.ai/voice-agents` (OAuth). Tool names are shown above without the `sarvam_tools_` prefix.

**Provisioned Throughput models** (`deepseekv4-pro`, `kimi-k3.1-pro`, `qwen38-27b`, `clef`, `embeddinggemma-2`) are not self-serve: contact Sarvam support ([support@sarvam.ai](mailto:support@sarvam.ai), [docs](https://docs.sarvam.ai/api/getting-started/help)) with the model you need and your expected volume. Without access `deepseekv4-pro` returns 400 and the others 404; `sarvam_list_models` shows which your key can use. The MCP turns those errors into this guidance. Exhausted credits surface as a quota error (HTTP 402).

## Configuration

| Env var | Default | Description |
|---|---|---|
| `SARVAM_API_KEY` | — | Required. API key from dashboard.sarvam.ai. |
| `SARVAM_API_BASE_URL` | `https://api.sarvam.ai` | Override for testing/staging. |
| `SARVAM_MCP_BASE_PATH` | `~/Desktop` | Where audio/document files land. |
| `SARVAM_AUDIO_OUTPUT_MODE` | `files` | `files` \| `resources` \| `both`. |

## Two namespaces

The server exposes tools across two namespaces:

- **`sarvam_tools_*`** — *runtime* tools. Call Sarvam APIs to do things (transcribe, speak, translate, etc.).
- **`sarvam_code_*`** — *builder* tools. Help you write code that uses Sarvam: docs, endpoint shapes, language lists, code snippets, starter projects.

## Development

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
mcp dev src/sarvam_mcp/server.py
```
