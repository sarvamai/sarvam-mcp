"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from sarvam_mcp.auth import StaticKeyProvider, set_auth


@pytest.fixture(autouse=True)
def _set_test_auth():
    """Every test gets a deterministic auth provider in its context."""
    set_auth(StaticKeyProvider("sk_test_key_for_unit_tests_abcd"))


@pytest.fixture
def tmp_base_path(tmp_path: Path) -> Path:
    """A throwaway base path for FileSink/BothSink tests."""
    return tmp_path / "out"
