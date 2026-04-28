# sarvam-mcp

Official Sarvam MCP server. Exposes every public Sarvam API — STT, TTS, Translate, Transliterate, Language ID, Text Analytics, LLM (Sarvam-M / 30B / 105B), Vision Document Intelligence, Pronunciation Dictionaries — as first-class MCP tools so any MCP-aware client (Claude Desktop, Claude Code, Cursor, Windsurf, Zed) can call Sarvam with zero boilerplate.

## Quickstart

The fastest way is the one-line installer at **[mcp.sarvam.ai](https://mcp.sarvam.ai)** — auto-detects your MCP clients and wires them up:

```bash
curl -fsSL https://mcp.sarvam.ai/install | bash
```

Or install manually:

```bash
pip install sarvam-mcp        # or:  uvx sarvam-mcp
```

Drop this JSON into your MCP client (same shape works in Cursor / Claude Desktop / Claude Code / Windsurf / Zed):

```json
{
  "mcpServers": {
    "sarvam": {
      "command": "uvx",
      "args": ["sarvam-mcp"]
    }
  }
}
```

**No API key required up front.** The server starts with auth deferred and **prompts you for the key on the first tool call** via MCP elicitation (Cursor / Claude Desktop will show a popup). The message links to [Key management](https://dashboard.sarvam.ai/key-management) — open it, copy an API key, and paste. The key gets saved to `~/.sarvam/credentials` (mode `0600`) so subsequent runs don't ask.

If your MCP client doesn't support elicitation, or you'd rather set the key ahead of time (easiest first):

```bash
# A) Env var in the MCP client config (no terminal in many IDEs) — add next to
#    "args" for the sarvam server:  "env": { "SARVAM_API_KEY": "sk_..." }

# B) Interactive setup (headless / when you prefer the terminal)
sarvam-mcp init

# C) Advanced: create ~/.sarvam/credentials yourself (avoid echoing a real key in shell history)
mkdir -p ~/.sarvam && printf 'api_key = sk_...\n' > ~/.sarvam/credentials && chmod 600 ~/.sarvam/credentials
```

### Per-client paths

- **Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Claude Code** — `claude mcp add sarvam -- uvx sarvam-mcp`
- **Cursor** — `~/.cursor/mcp.json`
- **Windsurf** — Cascade settings → MCP servers
- **Zed** — `settings.json` → `context_servers`

## Tools

All defaults below reflect the latest non-deprecated models live as of 2026-04-27.

| Tool | What it does | Default model | Other accepted |
|---|---|---|---|
| `sarvam_stt_transcribe` | Audio file → transcript (5 modes: transcribe, translate, verbatim, translit, codemix) | `saaras:v3` | `saarika:v2.5` (legacy) |
| `sarvam_stt_translate` | Audio → English text (DEPRECATED — use `stt_transcribe` with `mode=translate`) | `saaras:v2.5` | — |
| `sarvam_stt_batch_submit` | Long-audio job init (Azure SAS) | `saaras:v3` | `saarika:v2.5` (legacy) |
| `sarvam_stt_batch_status` | Long-audio job poll | — | — |
| `sarvam_tts_speak` | Text → audio file | `bulbul:v3` (speaker `priya`) | `bulbul:v3-beta`, `bulbul:v2` |
| `sarvam_tts_stream` | Text → streamed audio | `bulbul:v3` | `bulbul:v2` |
| `sarvam_translate` | Cross-language text translate | `mayura:v1` | `sarvam-translate:v1` (22 langs) |
| `sarvam_transliterate` | Script conversion | — | — |
| `sarvam_identify_language` | Language + script detect (11 languages) | — | — |
| `sarvam_text_analytics` | Typed Q&A over text | — | — |
| `sarvam_llm_complete` | Chat completions | `sarvam-30b` | `sarvam-105b`, `sarvam-m` (legacy) |
| `sarvam_vision_extract` | Document Intelligence (job-based pipeline) | Sarvam Vision (3B VLM) | — |
| `sarvam_vision_job_status` | Poll Document Intelligence job status | — | — |
| `sarvam_pronunciation_list` | List pronunciation dictionaries | — | — |
| `sarvam_pronunciation_get` | Get a pronunciation dictionary | — | — |
| `sarvam_pronunciation_create` | Create a pronunciation dictionary | — | — |
| `sarvam_pronunciation_delete` | Delete a pronunciation dictionary | — | — |

## Configuration

| Env var | Default | Description |
|---|---|---|
| `SARVAM_API_KEY` | — | Required. API key. Falls back to `~/.sarvam/credentials`. |
| `SARVAM_API_REGION` | `in` | Data residency region. |
| `SARVAM_API_BASE_URL` | `https://api.sarvam.ai` | Override for testing/staging. |
| `SARVAM_MCP_BASE_PATH` | `~/Desktop` | Where audio/document files land in `files` mode. |
| `SARVAM_AUDIO_OUTPUT_MODE` | `files` | `files` \| `resources` \| `both`. |

`~/.sarvam/credentials` format:

```ini
api_key = sk_...
region = in
```

## Two namespaces

The server exposes **27 tools** across two clean namespaces:

- **`sarvam_tools_*`** — *runtime* tools. Call Sarvam APIs at runtime to do things (transcribe audio, generate speech, translate text, ask Sarvam-M, run composite voice/dub/localize/recall workflows). 16 tools.
- **`sarvam_code_*`** — *builder* tools. Help an agent **write code that uses Sarvam**: search docs, look up endpoint shapes, list supported languages and speakers, validate request bodies, recommend models, fetch tested code snippets, scaffold starter projects (`simple-tts-cli`, `python-voice-bot`, `nextjs-translator`). 11 tools — no API key needed for most of them.

> **"Translate this paragraph to Hindi."** → `sarvam_tools_translate` invokes Sarvam.
>
> **"Build me an Indic translator app in Next.js."** → `sarvam_code_scaffold` writes a working starter project to disk; `sarvam_code_snippet` provides tested glue code.

## Companion repo

The **install website** at [mcp.sarvam.ai](https://mcp.sarvam.ai) lives in [`sarvamai/sarvam-mcp-website`](https://github.com/sarvamai/sarvam-mcp-website) (Next.js + Tatva, deployed on Sarvam k8s). This repo is just the Python package.

## Development

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q                              # 51 tests
mcp dev src/sarvam_mcp/server.py       # MCP Inspector
```
