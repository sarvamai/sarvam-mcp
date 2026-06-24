# Contributing to sarvam-mcp

Thanks for wanting to contribute! This guide gets you from zero to a running dev environment and merged PR.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- A Sarvam API key from [dashboard.sarvam.ai/key-management](https://dashboard.sarvam.ai/key-management)

## Setup

```bash
git clone https://github.com/sarvamai/sarvam-mcp.git
cd sarvam-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Store your API key so tests that hit the live API can authenticate:

```bash
mkdir -p ~/.sarvam
echo "api_key = sk_..." > ~/.sarvam/credentials
```

## Running tests

```bash
pytest -q
```

All tests must pass before opening a PR.

## Code style

We use **Ruff** for linting and formatting:

```bash
ruff check .
ruff format .
```

Key settings (from `pyproject.toml`):
- Line length: 110
- Target: Python 3.11
- Selected rules: E, F, I, B, UP, N, SIM

## Project structure

```
src/sarvam_mcp/
├── server.py          # FastMCP entry point
├── config.py          # Env vars + credentials
├── _registry.py       # ServerContext dataclass
├── auth/              # API key management
├── http/              # SarvamClient (httpx wrapper)
├── audio/             # AudioSink strategy
├── observability.py   # Latency + cost tracking
├── tools/             # Atomic tools (one API call each)
├── workflows/         # Composite tools (chained calls)
└── code/              # Builder tools (docs, snippets)
```

## Adding a new tool

1. Create a module in `src/sarvam_mcp/tools/` (or `workflows/` for composite tools).
2. Export a `register(mcp: FastMCP)` function.
3. Start the tool body with `sc = await ready_ctx(ctx)`.
4. Include an `observability` dict in the response.
5. Add tests in `tests/`.

## Commit conventions

- Keep commits focused — one logical change per commit.
- Use short, lowercase commit messages describing the change (e.g. `add pronunciation dictionary tools`).

## Opening a PR

1. Fork the repo and create a feature branch from `main`.
2. Make your changes and ensure `pytest -q` passes.
3. Run `ruff check . && ruff format --check .` to verify style.
4. Push and open a PR against `main`.

## Releasing

Releases are automated via GitHub Actions. Maintainers bump the version in `pyproject.toml` and either push a `v*-qa` tag or manually trigger the publish workflow.

## Questions?

Open an issue or reach out at support@sarvam.ai.
