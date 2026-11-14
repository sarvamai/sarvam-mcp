from __future__ import annotations

from pathlib import Path

from sarvam_mcp.workflows.recall import _gather_files


def test_gather_files_limits_to_max_files(tmp_path: Path):
    folder = tmp_path / "documents"
    folder.mkdir()
    for index in range(10):
        (folder / f"note_{index}.txt").write_text(f"content {index}")

    results = _gather_files([str(folder)], max_files=4)
    assert len(results) == 4


def test_gather_files_filters_unsupported_extensions(tmp_path: Path):
    folder = tmp_path / "mixed"
    folder.mkdir()
    (folder / "supported.txt").write_text("valid text")
    (folder / "unsupported.bin").write_bytes(b"\x00\x01")

    results = _gather_files([str(folder)], max_files=10)
    assert len(results) == 1
    assert results[0].name == "supported.txt"


def test_gather_files_direct_file_path(tmp_path: Path):
    file_path = tmp_path / "single_file.md"
    file_path.write_text("markdown content")

    results = _gather_files([str(file_path)], max_files=5)
    assert len(results) == 1
    assert results[0] == file_path
