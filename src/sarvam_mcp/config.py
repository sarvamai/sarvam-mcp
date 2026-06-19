"""Configuration: env vars, ~/.sarvam/credentials, output mode."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

OutputMode = Literal["files", "resources", "both"]

DEFAULT_BASE_URL = "https://api.sarvam.ai"
DEFAULT_BASE_PATH = "~/Desktop"
DEFAULT_OUTPUT_MODE: OutputMode = "files"


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration. Built once at server startup."""

    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    base_path: Path = field(default_factory=lambda: Path(DEFAULT_BASE_PATH).expanduser())
    output_mode: OutputMode = DEFAULT_OUTPUT_MODE

    @classmethod
    def load(cls) -> Config:
        """Resolve config from env vars, falling back to ~/.sarvam/credentials."""
        creds = _read_credentials_file()

        api_key = os.environ.get("SARVAM_API_KEY") or creds.get("api_key")
        base_url = os.environ.get("SARVAM_API_BASE_URL", DEFAULT_BASE_URL)
        base_path_str = os.environ.get("SARVAM_MCP_BASE_PATH", DEFAULT_BASE_PATH)
        mode_str = os.environ.get("SARVAM_AUDIO_OUTPUT_MODE", DEFAULT_OUTPUT_MODE).lower()

        if mode_str not in ("files", "resources", "both"):
            raise ValueError(
                f"SARVAM_AUDIO_OUTPUT_MODE must be one of 'files', 'resources', 'both'; "
                f"got {mode_str!r}"
            )

        base_path = Path(base_path_str).expanduser()

        return cls(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            base_path=base_path,
            output_mode=mode_str,  # type: ignore[arg-type]
        )


def _read_credentials_file() -> dict[str, str]:
    """Parse ~/.sarvam/credentials (simple key=value format). Missing file -> empty dict."""
    path = Path("~/.sarvam/credentials").expanduser()
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out
