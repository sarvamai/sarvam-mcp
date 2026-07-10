"""Windows credential-permission hardening must fail loudly, not silently.

On POSIX ``os.chmod`` raises on failure; the Windows ``icacls`` path used to
swallow every failure, leaving the API-key file with inherited permissions and
no signal. These tests pin the warning behaviour (and run on any platform by
calling the Windows helper directly).
"""

from __future__ import annotations

from sarvam_mcp.tools import auth as auth_mod
from sarvam_mcp.tools.auth import _restrict_permissions_windows


class _FakeResult:
    def __init__(self, returncode: int, stderr: str = "", stdout: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


def test_warns_when_username_missing(monkeypatch, caplog, tmp_path):
    monkeypatch.delenv("USERNAME", raising=False)
    called = False

    def _should_not_run(*args, **kwargs):
        nonlocal called
        called = True
        return _FakeResult(0)

    monkeypatch.setattr(auth_mod.subprocess, "run", _should_not_run)

    path = tmp_path / "credentials"
    path.write_text("api_key = sk_x\n")
    with caplog.at_level("WARNING"):
        _restrict_permissions_windows(path)

    assert not called, "icacls must not run without a username"
    assert any("restrict permissions" in r.message.lower() for r in caplog.records)


def test_warns_when_icacls_fails(monkeypatch, caplog, tmp_path):
    monkeypatch.setenv("USERNAME", "tester")
    monkeypatch.setattr(
        auth_mod.subprocess, "run", lambda *a, **k: _FakeResult(5, stderr="Access is denied.")
    )

    path = tmp_path / "credentials"
    path.write_text("api_key = sk_x\n")
    with caplog.at_level("WARNING"):
        _restrict_permissions_windows(path)

    messages = " ".join(r.message.lower() for r in caplog.records)
    assert "restrict permissions" in messages
    assert "access is denied" in messages


def test_silent_on_success(monkeypatch, caplog, tmp_path):
    monkeypatch.setenv("USERNAME", "tester")
    monkeypatch.setattr(auth_mod.subprocess, "run", lambda *a, **k: _FakeResult(0))

    path = tmp_path / "credentials"
    path.write_text("api_key = sk_x\n")
    with caplog.at_level("WARNING"):
        _restrict_permissions_windows(path)

    assert not caplog.records, "success path must not warn"
