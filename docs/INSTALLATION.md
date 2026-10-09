# Installing sarvam-mcp

Step-by-step setup for every supported environment. Pick your client below and follow the steps top to bottom.

The server runs locally over stdio — your MCP client spawns it as a subprocess. There is nothing to host and no port to open.

## Before you start

1. **Get an API key** — sign up or log in at [dashboard.sarvam.ai/key-management](https://dashboard.sarvam.ai/key-management) and copy your key (`sk_...`).
2. **Pick a run method** — every client config below uses one of these two:

   | Method | Command in config | Prerequisite |
   |---|---|---|
   | **uvx** (recommended) | `"command": "uvx", "args": ["sarvam-mcp"]` | [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed |
   | **pip** | `"command": "sarvam-mcp"` | Python 3.11+, then `pip install sarvam-mcp` |

   `uvx` needs no prior install — it downloads and runs the latest published version in an isolated environment, which also avoids `PATH`/pyenv conflicts. The examples below use `uvx`; to use the pip variant instead, swap the `command`/`args` accordingly.

3. **Provide the key** — either inline in the client config (shown in each example as `"env": { "SARVAM_API_KEY": "sk_..." }`) or once globally in `~/.sarvam/credentials`:

   ```ini
   api_key = sk_...
   region = in
   ```

   If you use the credentials file, you can drop the `env` block from every config below.

---

## Cursor

### One-click (recommended)

Click the install link — Cursor opens and asks you to confirm:

[![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=sarvam&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJzYXJ2YW0tbWNwIl19)

If the button opens a tab that closes without launching Cursor (the browser blocked the app prompt), paste this deeplink into your browser's address bar instead:

```
cursor://anysphere.cursor-deeplink/mcp/install?name=sarvam&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJzYXJ2YW0tbWNwIl19
```

Then set your API key once in `~/.sarvam/credentials` (see above), or add the `env` block via Cursor Settings → MCP → sarvam → edit.

### Manual

1. Open (or create) the config file:
   - Global: `~/.cursor/mcp.json` (macOS/Linux) · `%USERPROFILE%\.cursor\mcp.json` (Windows)
   - Per-project: `.cursor/mcp.json` in the repo root
2. Add:

   ```json
   {
     "mcpServers": {
       "sarvam": {
         "command": "uvx",
         "args": ["sarvam-mcp"],
         "env": { "SARVAM_API_KEY": "sk_..." }
       }
     }
   }
   ```

3. Reload Cursor (or toggle the server in Settings → MCP).
4. Verify: Settings → MCP shows **sarvam** with a green dot and its tool list.

## Claude Code

One command — no JSON:

```bash
# Available in every project
claude mcp add --scope user sarvam --env SARVAM_API_KEY=sk_... -- uvx sarvam-mcp

# Or only for the current project
claude mcp add sarvam --env SARVAM_API_KEY=sk_... -- uvx sarvam-mcp
```

Verify inside a Claude Code session with `/mcp` — **sarvam** should be listed as connected.

## Claude Desktop

1. Open the config file (create it if missing):
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
2. Add:

   ```json
   {
     "mcpServers": {
       "sarvam": {
         "command": "uvx",
         "args": ["sarvam-mcp"],
         "env": { "SARVAM_API_KEY": "sk_..." }
       }
     }
   }
   ```

3. Quit and reopen Claude Desktop (a full restart is required).
4. Verify: the tools icon (🔨) in the chat input lists the Sarvam tools.

## VS Code (GitHub Copilot)

One-liner:

```bash
code --add-mcp '{"name":"sarvam","command":"uvx","args":["sarvam-mcp"],"env":{"SARVAM_API_KEY":"sk_..."}}'
```

Or manually in `.vscode/mcp.json` (note the top-level key is `servers`, not `mcpServers`):

```json
{
  "servers": {
    "sarvam": {
      "command": "uvx",
      "args": ["sarvam-mcp"],
      "env": { "SARVAM_API_KEY": "sk_..." }
    }
  }
}
```

Verify: Copilot Chat → Agent mode → tools picker shows the Sarvam tools.

## Windsurf

1. Open `~/.codeium/windsurf/mcp_config.json` (or Cascade → MCP servers → *Manage* → *View raw config*).
2. Add the same `mcpServers` block as the Cursor manual example.
3. Click **Refresh** in the Cascade MCP panel.

## Zed

Add to `settings.json` (Cmd/Ctrl+`,`):

```json
{
  "context_servers": {
    "sarvam": {
      "command": {
        "path": "uvx",
        "args": ["sarvam-mcp"],
        "env": { "SARVAM_API_KEY": "sk_..." }
      }
    }
  }
}
```

## Codex CLI (OpenAI)

```bash
codex mcp add sarvam --env SARVAM_API_KEY=sk_... -- uvx sarvam-mcp
```

Or in `~/.codex/config.toml`:

```toml
[mcp_servers.sarvam]
command = "uvx"
args = ["sarvam-mcp"]
env = { SARVAM_API_KEY = "sk_..." }
```

## Gemini CLI

```bash
gemini mcp add sarvam -e SARVAM_API_KEY=sk_... uvx sarvam-mcp
```

Or in `~/.gemini/settings.json` under `mcpServers` (same shape as the Cursor example).

## Cline / Roo Code (VS Code extensions)

1. Open the extension's MCP settings (Cline: MCP Servers icon → *Configure MCP Servers*).
2. Add the same `mcpServers` block as the Cursor manual example to `cline_mcp_settings.json`.
3. The server list refreshes automatically.

## Continue

Add to `~/.continue/config.yaml`:

```yaml
mcpServers:
  - name: sarvam
    command: uvx
    args:
      - sarvam-mcp
    env:
      SARVAM_API_KEY: sk_...
```

## LM Studio

1. Program (top right) → *Install* → *Edit mcp.json*.
2. Add the same `mcpServers` block as the Cursor manual example.
3. Toggle the server on; tools appear in chats with tool-capable models.

---

## Verify your install

Ask your assistant something that exercises a Sarvam tool, e.g.:

> Translate "good morning" to Hindi using sarvam.

Or test the server outside any client with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uvx sarvam-mcp
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `spawn uvx ENOENT` / `command not found: uvx` | Install `uv` (`curl -LsSf https://astral.sh/uv/install.sh \| sh` on macOS/Linux, `winget install astral-sh.uv` on Windows), then restart the client so it picks up the new `PATH`. |
| `command not found: sarvam-mcp` after `pip install` | Your `pip` belongs to a different Python than your shell `PATH` (common with pyenv/conda). Use the `uvx` config instead, or point `command` at the absolute path printed by `pip show -f sarvam-mcp`. |
| Stale version runs after upgrading | A leftover copy may shadow the new one — check `which -a sarvam-mcp` and remove old binaries (e.g. in `~/.local/bin`). `uvx` always runs the latest published version. |
| Auth errors on tool calls | Confirm the key: `SARVAM_API_KEY` env var in the client config, or `~/.sarvam/credentials`. The env var wins if both are set. |
| Server runs then "hangs" in a terminal | Expected — stdio servers wait for a client on stdin. Don't run `sarvam-mcp` manually; let the client spawn it. |
| First call is slow with `uvx` | Cold start: `uvx` downloads the package on first run. Subsequent runs use the cache. Pre-warm with `uv tool install sarvam-mcp`. |

## Updating

- **uvx**: nothing to do for cache refreshes on new releases; force the latest with `uvx sarvam-mcp@latest` or clear the cache (`uv cache clean sarvam-mcp`).
- **pip**: `pip install --upgrade sarvam-mcp`.
