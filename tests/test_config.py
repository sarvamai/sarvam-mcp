"""Config resolution tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sarvam_mcp.config import Config, _read_credentials_file


def _write_creds(home: Path, body: str) -> None:
    sarvam_dir = home / ".sarvam"
    sarvam_dir.mkdir(parents=True, exist_ok=True)
    (sarvam_dir / "credentials").write_text(body)


def _set_home(monkeypatch, tmp_path: Path) -> None:
    """Point ``~`` at tmp_path for Path.expanduser() on both POSIX and Windows.

    ``expanduser()`` reads HOME on POSIX but USERPROFILE (not HOME) on Windows,
    so both must be set for these tests to be platform-independent.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def test_credentials_file_parses_quoted_and_comments(tmp_path, monkeypatch):
    _set_home(monkeypatch, tmp_path)
    _write_creds(
        tmp_path,
        '# leading comment\napi_key = "sk_quoted"\n\n  ignored line\n',
    )
    parsed = _read_credentials_file()
    assert parsed["api_key"] == "sk_quoted"
    assert "ignored line" not in parsed


def test_invalid_output_mode_raises(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SARVAM_AUDIO_OUTPUT_MODE", "magic")
    with pytest.raises(ValueError, match="SARVAM_AUDIO_OUTPUT_MODE"):
        Config.load()


def test_base_path_expands(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    target = tmp_path / "out"
    monkeypatch.setenv("SARVAM_MCP_BASE_PATH", str(target))
    cfg = Config.load()
    assert cfg.base_path == Path(target)


def test_api_key_from_env(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SARVAM_API_KEY", "sk_from_env")
    cfg = Config.load()
    assert cfg.api_key == "sk_from_env"


def test_api_key_from_credentials(tmp_path, monkeypatch):
    _set_home(monkeypatch, tmp_path)
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    _write_creds(tmp_path, "api_key = sk_from_file\n")
    cfg = Config.load()
    assert cfg.api_key == "sk_from_file"
