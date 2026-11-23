"""Regression tests for open GitHub issues #59/#73/#20/#16, #80, #74, #70, #86, #125, #48, #83."""

from __future__ import annotations

import base64
import json
import stat
import sys
import tomllib
from pathlib import Path

import httpx
import pytest

from sarvam_mcp.audio.sinks import FileSink
from sarvam_mcp.tools._common import resolve_file_input
from sarvam_mcp.workflows import localize, recall
from tests.tools.conftest import call_tool

ROOT = Path(__file__).resolve().parents[2]


# ---- #80 strict base64 ----------------------------------------------------


@pytest.mark.parametrize("payload", ["!!!!", "aGVsbG8=!!!!", "not base64 at all %%%"])
async def test_malformed_base64_rejected(payload):
    with pytest.raises(ValueError, match="not valid base64|empty"):
        async with resolve_file_input(file_base64=payload, filename="a.wav"):
            pass


async def test_valid_base64_roundtrips_and_temp_file_removed():
    async with resolve_file_input(
        file_base64=base64.b64encode(b"hello").decode(), filename="a.wav"
    ) as p:
        assert p.read_bytes() == b"hello"
        kept = p
    assert not kept.exists()


# ---- #59 / #73 / #20 temp file closed + removed on every failure path -----


async def test_oversize_base64_cleans_temp_file(monkeypatch, tmp_path):
    created: list[Path] = []
    import tempfile

    real = tempfile.NamedTemporaryFile

    def spy(*a, **kw):
        f = real(*a, **kw)
        created.append(Path(f.name))
        return f

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy)
    with pytest.raises(ValueError, match="exceeds"):
        async with resolve_file_input(
            file_base64=base64.b64encode(b"x" * 100).decode(), filename="a.wav", max_bytes=10
        ):
            pass
    assert created and not created[0].exists()


async def test_download_failure_closes_handle_and_cleans_up(monkeypatch, httpx_mock):
    import tempfile

    handles = []
    real = tempfile.NamedTemporaryFile

    def spy(*a, **kw):
        f = real(*a, **kw)
        handles.append(f)
        return f

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy)
    httpx_mock.add_response(url="https://example.com/a.wav", status_code=404)
    with pytest.raises(httpx.HTTPStatusError):
        async with resolve_file_input(file_url="https://example.com/a.wav", filename="a.wav"):
            pass
    assert handles and handles[0].closed
    assert not Path(handles[0].name).exists()


# ---- #74 FileSink containment --------------------------------------------


async def test_file_sink_refuses_escape(tmp_path):
    sink = FileSink(tmp_path / "out")
    ok = await sink.store(b"a", filename="a.wav", mime_type="audio/wav")
    assert Path(ok.file_path).parent == (tmp_path / "out").resolve()
    for bad in ("../evil.wav", "/tmp/evil.wav", "sub/../../evil.wav"):
        with pytest.raises(ValueError, match="outside"):
            await sink.store(b"a", filename=bad, mime_type="audio/wav")
    assert not (tmp_path / "evil.wav").exists()


# ---- #70 recall stops walking at max_files --------------------------------


def test_gather_files_is_bounded_and_sorted(tmp_path, monkeypatch):
    for d in ("a", "b", "c"):
        (tmp_path / d).mkdir()
        for i in range(5):
            (tmp_path / d / f"{i}.wav").write_bytes(b"x")
    visited = []
    real = recall._walk_sorted

    def counting(root):
        for p in real(root):
            visited.append(p)
            yield p

    monkeypatch.setattr(recall, "_walk_sorted", counting)
    out = recall._gather_files([str(tmp_path)], max_files=3)
    assert [p.name for p in out] == ["0.wav", "1.wav", "2.wav"]
    assert all(p.parent.name == "a" for p in out)
    assert len(set(visited)) <= 3  # did not walk the whole 15-file tree first


# ---- #86 credentials never world-readable ---------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_save_key_creates_private_file_and_dir(tmp_path, monkeypatch):
    from sarvam_mcp.tools import auth

    monkeypatch.setattr(auth, "CREDENTIALS_PATH", tmp_path / ".sarvam" / "credentials")
    auth._save_key("sk_abcdefghijklmnopqrstuvwx")
    path = auth.CREDENTIALS_PATH
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert "api_key = sk_abcdefghijklmnopqrstuvwx" in path.read_text()
    auth._save_key("sk_zzzzzzzzzzzzzzzzzzzzzzzz")  # rotation keeps mode
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not path.with_suffix(".tmp").exists()


# ---- #125 localize top-level JSON string ----------------------------------


async def test_localize_top_level_json_string(make_server, httpx_mock, tmp_path):
    src = tmp_path / "messages.en-IN.json"
    src.write_text(json.dumps("Hello"))
    httpx_mock.add_response(
        url="https://api.sarvam.ai/translate",
        json={"translated_text": "नमस्ते", "source_language_code": "en-IN"},
    )
    out = await call_tool(
        make_server(localize),
        "sarvam_tools_localize",
        source_path=str(src),
        target_language_code="hi-IN",
    )
    assert out["strings_translated"] == 1
    assert json.loads(Path(out["output_path"]).read_text()) == "नमस्ते"


async def test_localize_nested_still_works(make_server, httpx_mock, tmp_path):
    src = tmp_path / "m.en-IN.json"
    src.write_text(json.dumps({"a": {"b": "Hi"}, "n": 3}))
    httpx_mock.add_response(
        url="https://api.sarvam.ai/translate",
        json={"translated_text": "नमस्ते", "source_language_code": "en-IN"},
    )
    out = await call_tool(
        make_server(localize),
        "sarvam_tools_localize",
        source_path=str(src),
        target_language_code="hi-IN",
    )
    assert json.loads(Path(out["output_path"]).read_text()) == {"a": {"b": "नमस्ते"}, "n": 3}


# ---- #48 server.json in sync, #83 no obsolete batch path ------------------


def test_server_json_matches_pyproject_version():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    server = json.loads((ROOT / "server.json").read_text())
    assert server["version"] == version
    assert all(p["version"] == version for p in server["packages"])


def test_no_obsolete_batch_stt_path_in_builder_text():
    for f in (ROOT / "src" / "sarvam_mcp" / "code").glob("*.py"):
        assert "/speech-to-text/job/init" not in f.read_text(), f.name
