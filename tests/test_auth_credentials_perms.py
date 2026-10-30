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

    Captures the mode of every file in the credentials directory at the moment
    ``os.chmod`` is first called, i.e. the state a concurrent local reader would
    have seen. The original implementation wrote the key via ``Path.write_text``
    and only tightened it afterwards, so the secret sat at 0o644 under the
    default umask until the chmod landed.

    Deliberately does not spy on ``os.open``: that would assert *how* the file
    is created rather than that it is never exposed, and would pass vacuously
    against any implementation using a different write API.
    """
    observed: dict[str, int] = {}
    real_chmod = os.chmod

    def record_dir_state():
        d = creds_path.parent
        if not d.exists():
            return
        for child in d.iterdir():
            if child.is_file() and child.name not in observed:
                observed[child.name] = stat.S_IMODE(child.stat().st_mode)

    def spy(path, mode, *args, **kwargs):
        record_dir_state()
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", spy)
    auth_tool._save_key(KEY)
    record_dir_state()

    assert observed, "no credentials file was ever observed on disk"
    for name, mode in observed.items():
        assert not mode & (stat.S_IRGRP | stat.S_IROTH), (
            f"{name} existed at {oct(mode)} — readable by group/other before it was locked down"
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


def test_stale_temp_file_does_not_break_the_write(creds_path):
    """A leftover .tmp from a crashed run must be replaced, not fatal."""
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = creds_path.with_suffix(".tmp")
    tmp.write_text("api_key = sk_stale\n")

    auth_tool._save_key(KEY)

    assert f"api_key = {KEY}" in creds_path.read_text()
    assert _mode(creds_path) == 0o600
    assert not tmp.exists()


def test_temp_file_vanishing_mid_write_is_not_an_error(creds_path, monkeypatch):
    """Regression guard for the check-then-unlink TOCTOU.

    Simulates the racing reaper: the temp file is still present when
    ``_write_private`` decides to remove it, but something else (a tmpreaper, a
    concurrent save) has deleted it by the time the unlink lands. The old
    ``if path.exists(): path.unlink()`` pair surfaced that as FileNotFoundError;
    ``missing_ok=True`` absorbs it and lets O_EXCL do the real enforcement.

    Patches ``os.unlink`` — the syscall ``Path.unlink`` delegates to — rather
    than the Path method, so the fixture's CREDENTIALS_PATH patch stays intact
    and the test cannot escape tmp_path onto the real ~/.sarvam.
    """
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = creds_path.with_suffix(".tmp")
    tmp.write_text("api_key = sk_stale\n")

    real_unlink = os.unlink
    raced = {"done": False}

    def vanishing_unlink(path, *args, **kwargs):
        if not raced["done"] and os.fspath(path) == str(tmp):
            raced["done"] = True
            real_unlink(path)  # the reaper wins the race
            raise FileNotFoundError(path)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", vanishing_unlink)
    auth_tool._save_key(KEY)

    assert raced["done"], "the simulated race never triggered"
    assert f"api_key = {KEY}" in creds_path.read_text()
    assert _mode(creds_path) == 0o600


def test_directory_chmod_failure_is_surfaced(creds_path, monkeypatch):
    """A directory we cannot lock down must fail loudly, not report success."""
    real_chmod = os.chmod

    def failing_chmod(path, mode, *args, **kwargs):
        if os.path.isdir(path):
            raise PermissionError(path)
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", failing_chmod)

    with pytest.raises(PermissionError):
        auth_tool._save_key(KEY)
