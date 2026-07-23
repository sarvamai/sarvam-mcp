# sarvam-mcp

Official Sarvam MCP server. Exposes every public Sarvam API — STT, TTS, Translate, Transliterate, Language ID, Text Analytics, LLM (30B / 105B), Vision Document Intelligence, Pronunciation Dictionaries — as first-class MCP tools so any MCP-aware client (Claude Desktop, Claude Code, Cursor, Windsurf, Zed) can call Sarvam with zero boilerplate.

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

> **Note:** All `sarvam_tools_*` tools require `SARVAM_API_KEY` to be set. See [Configuration](#configuration) section for setup details.
>

| Tool | What it does | Default model |
|---|---|---|
| `sarvam_stt_transcribe` | Audio file → transcript (5 modes) | `saaras:v3` |
| `sarvam_tts_speak` | Text → audio file | `bulbul:v3` |
| `sarvam_tts_stream` | Text → streamed audio | `bulbul:v3` |
| `sarvam_translate` | Cross-language text translate | `mayura:v1` |
| `sarvam_transliterate` | Script conversion | — |
| `sarvam_identify_language` | Language + script detect | — |
| `sarvam_text_analytics` | Typed Q&A over text | — |
| `sarvam_llm_complete` | Chat completions | `sarvam-30b` |
| `sarvam_vision_extract` | Document Intelligence | Sarvam Vision |
| `sarvam_vision_job_status` | Poll Document Intelligence job | — |
| `sarvam_pronunciation_list` | List pronunciation dictionaries | — |
| `sarvam_pronunciation_get` | Get a pronunciation dictionary | — |
| `sarvam_pronunciation_create` | Create a pronunciation dictionary | — |
| `sarvam_pronunciation_delete` | Delete a pronunciation dictionary | — |

## Configuration

| Env var | Default | Description |
|---|---|---|
| `SARVAM_API_KEY` | — | Required. API key from dashboard.sarvam.ai. |
| `SARVAM_API_BASE_URL` | `https://api.sarvam.ai` | Override for testing/staging. |
| `SARVAM_MCP_BASE_PATH` | `~/Desktop` | Where audio/document files land. |
| `SARVAM_AUDIO_OUTPUT_MODE` | `files` | `files` \| `resources` \| `both`. |

## Two namespaces

The server exposes tools across two namespaces:

- **`sarvam_tools_*`** — *runtime* tools. Call Sarvam APIs to do things (transcribe, speak, translate, etc.). **Requires `SARVAM_API_KEY`.**
- **`sarvam_code_*`** — *builder* tools. Help you write code that uses Sarvam: docs, endpoint shapes, language lists, code snippets, starter projects.

## Development

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
mcp dev src/sarvam_mcp/server.py
```
