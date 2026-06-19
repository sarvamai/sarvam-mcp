# Agent Guide — sarvam-mcp

## Tool Namespace Routing

This MCP server exposes two tool namespaces plus a key management tool:

### `sarvam_tools_set_api_key` — API Key Management

Use when the user needs to set or update their API key:

- If any tool returns an auth error, call `sarvam_tools_set_api_key` — it will direct the user to the dashboard and accept their pasted key.
- The key is saved globally to `~/.sarvam/credentials` so it persists across sessions.
- Same tool handles first-time setup and key rotation.

### `sarvam_tools_*` — Runtime (do the thing NOW)

Use when the user wants to **perform** a Sarvam action in the current conversation:

- "Translate this paragraph to Tamil"
- "Read this audio file and transcribe it"
- "Say this in Hindi" (TTS)
- "Dub this audio into Kannada"

These tools call the Sarvam API live and return results (text, audio files, etc.).

Includes composite workflows that chain multiple API calls:

- `sarvam_tools_voice` — audio in → STT → LLM reply → TTS → audio out
- `sarvam_tools_dub` — audio in → STT → Translate → TTS (dubbing)
- `sarvam_tools_localize` — translate an entire i18n string-table file
- `sarvam_tools_recall` — audio in → STT → LLM summary

### `sarvam_code_*` — Build-time (help the user WRITE code)

Use when the user is **building an app** that calls Sarvam APIs:

- "How do I call the TTS endpoint from Python?"
- "Which languages does STT support?"
- "What TTS speakers are available for bulbul:v3?"
- "What's the request shape for /translate?"

These tools return documentation, code snippets, API reference, and project templates. They do NOT call the Sarvam API at runtime.

### Decision rule

> Is the user asking you to **use** Sarvam right now, or to **write code** that uses Sarvam?
>
> - Use Sarvam → `sarvam_tools_*`
> - Write code that uses Sarvam → `sarvam_code_*`

## Authentication

Authentication uses **API keys**.

- **Setup:** Set `SARVAM_API_KEY` in the MCP client config JSON (`"env": {"SARVAM_API_KEY": "sk_..."}`), or store it in `~/.sarvam/credentials` as `api_key = sk_...`.
- **Get a key:** Sign up / log in at [dashboard.sarvam.ai/key-management](https://dashboard.sarvam.ai/key-management) and copy your API key.
- **How it works:** The server reads the key from the env var (or credentials file) at startup and sends it as `api-subscription-key` header on all outbound Sarvam API calls.

If a tool returns an auth error, the user needs to check their API key is set correctly.

## Architecture

```
src/sarvam_mcp/
├── server.py          # FastMCP entry point, registers all tools
├── config.py          # Env vars + ~/.sarvam/credentials
├── _registry.py       # ServerContext dataclass (config + client + sink)
├── auth/              # API key management
│   ├── api_key.py     # StaticKeyProvider (produces api-subscription-key headers)
│   ├── context.py     # ContextVar for current provider
│   └── elicit.py      # Auth gate — errors if no key is set
├── http/              # SarvamClient (httpx wrapper, retry, error mapping)
├── audio/             # AudioSink strategy (files / resources / both)
├── observability.py   # Latency + cost + request-id tracking
├── tools/             # Atomic tools — one Sarvam API call each
├── workflows/         # Composite tools — chain multiple atomic calls
└── code/              # Builder tools — docs, snippets
    ├── _data.py       # Hard-coded reference tables
    └── _snippets.py   # Embedded code examples
```

## Conventions

- Every tool module exports `register(mcp: FastMCP)`.
- Every tool that calls the Sarvam API starts with `sc = await ready_ctx(ctx)`.
- Every tool response includes an `observability` dict with latency, request IDs, and credit usage.
- `_data.py` and `_snippets.py` are reference tables — update carefully.
- Run `pytest -q` before committing.

**Packaging note:** Default to `pip install sarvam-mcp` or `uvx sarvam-mcp`. **Suggest `git clone` (and a from-source / editable install) only if the user does not have `pip`** — not as a routine alternative. Contributors still clone to develop and run tests.

**Platforms:** The server targets **macOS, Windows, and Linux** (Python 3.11+). When helping with setup, prefer OS-agnostic instructions (`pip` / `uvx`, same MCP JSON); call out Windows vs Unix **config file paths** only when the user's client or OS is known (see README).
