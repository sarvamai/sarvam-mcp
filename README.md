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

| Tool | What it does | Default model |
|---|---|---|
| `sarvam_tools_stt_transcribe` | Audio file → transcript (5 modes) | `saaras:v3` |
| `sarvam_tools_stt_translate` | Deprecated legacy speech → English wrapper; use `sarvam_tools_stt_transcribe` with `mode="translate"` | `saaras:v2.5` |
| `sarvam_tools_stt_batch_submit` | Long-audio STT batch pipeline | `saaras:v3` |
| `sarvam_tools_stt_batch_status` | Poll a batch STT job | — |
| `sarvam_tools_tts_speak` | Text → audio file | `bulbul:v3` |
| `sarvam_tools_tts_stream` | Text → streamed audio | `bulbul:v3` |
| `sarvam_tools_translate` | Cross-language text translate | `mayura:v1` |
| `sarvam_tools_transliterate` | Script conversion | — |
| `sarvam_tools_identify_language` | Language + script detect | — |
| `sarvam_tools_text_analytics` | Typed Q&A over text | — |
| `sarvam_tools_llm_complete` | Chat completions | `sarvam-30b` |
| `sarvam_tools_vision_extract` | Document Intelligence | Sarvam Vision |
| `sarvam_tools_vision_job_status` | Poll Document Intelligence job | — |
| `sarvam_tools_pronunciation_list` | List pronunciation dictionaries | — |
| `sarvam_tools_pronunciation_get` | Get a pronunciation dictionary | — |
| `sarvam_tools_pronunciation_create` | Create a pronunciation dictionary | — |
| `sarvam_tools_pronunciation_delete` | Delete a pronunciation dictionary | — |
| `sarvam_tools_voice` | Audio → STT → LLM reply → TTS | `saaras:v3` / `sarvam-30b` / `bulbul:v3` |
| `sarvam_tools_dub` | Audio → STT → translate → TTS | `saaras:v3` / `mayura:v1` / `bulbul:v3` |
| `sarvam_tools_localize` | Translate string-table files | `sarvam-translate:v1` |
| `sarvam_tools_recall` | Grounded Q&A over text/audio files | `sarvam-30b` |

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
