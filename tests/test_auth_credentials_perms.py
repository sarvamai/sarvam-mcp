"""The credentials file must never be readable by other local users.

``sarvam_tools_set_api_key`` writes a long-lived secret to
``~/.sarvam/credentials``. These tests pin the *ordering* guarantee: the key
must be owner-only from the instant it first exists on disk, not merely by the
time ``_save_key`` returns.
"""

from __future__ import annotations

import os
import stat
import sys

import pytest

from sarvam_mcp.tools import auth as auth_tool

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX permission bits; the Windows branch uses icacls.",
)

KEY = "sk_test_credentials_permissions"


@pytest.fixture
def creds_path(tmp_path, monkeypatch):
    path = tmp_path / ".sarvam" / "credentials"
    monkeypatch.setattr(auth_tool, "CREDENTIALS_PATH", path)
    return path


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_saved_credentials_are_owner_only(creds_path):
    auth_tool._save_key(KEY)
    assert _mode(creds_path) == 0o600


def test_credentials_dir_is_not_world_traversable(creds_path):
    auth_tool._save_key(KEY)
    assert _mode(creds_path.parent) == 0o700


def test_key_is_never_written_at_permissive_mode(creds_path, monkeypatch):
    """Regression guard for the write-then-chmod race.

    Records the mode at the moment the file is first created. The original
    implementation called ``Path.write_text`` and only chmod-ed afterwards,
    leaving the secret at 0o644 under the default umask in between.
    """
    observed: list[int] = []
    real_open = os.open

    def spy(path, flags, mode=0o777, *args, **kwargs):
        fd = real_open(path, flags, mode, *args, **kwargs)
        if str(path).endswith(".tmp") and (flags & os.O_CREAT):
            observed.append(stat.S_IMODE(os.fstat(fd).st_mode))
        return fd

    monkeypatch.setattr(os, "open", spy)
    auth_tool._save_key(KEY)

    assert observed, "temp credentials file was never created via os.open"
    for mode in observed:
        assert not mode & (stat.S_IRGRP | stat.S_IROTH), (
            f"key file was created at {oct(mode)} — readable by group/other"
        )


def test_umask_cannot_widen_permissions(creds_path):
    """A permissive umask must not loosen the credentials file."""
    old = os.umask(0o000)
    try:
        auth_tool._save_key(KEY)
    finally:
        os.umask(old)
    assert _mode(creds_path) == 0o600


def test_existing_settings_are_preserved(creds_path):
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text("# header\napi_key = sk_old\nregion = in-south-1\n")

    auth_tool._save_key(KEY)

    text = creds_path.read_text()
    assert f"api_key = {KEY}" in text
    assert "region = in-south-1" in text
    assert "sk_old" not in text
    assert _mode(creds_path) == 0o600


def test_overwriting_an_existing_permissive_file_tightens_it(creds_path):
    """Users upgrading from an affected version must be repaired, not left as-is."""
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text("api_key = sk_old\n")
    os.chmod(creds_path, 0o644)

    auth_tool._save_key(KEY)

    assert _mode(creds_path) == 0o600
