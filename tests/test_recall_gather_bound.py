"""Behavioral test for the _gather_files lazy-cap fix.

No timing assertions (flaky in CI). We count how many entries `rglob`
actually yields. With `sorted(p.rglob("*"))`, the full generator is
drained (~505 entries) before the max_files cap can trigger. With the
lazy `islice` cap, iteration stops after ~max_files supported files.

Technique: monkeypatch the `Path` symbol imported into the recall module
with a subclass whose rglob counts yields.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sarvam_mcp.workflows.recall as recall


class CountingPath(type(Path())):
    """Path subclass whose rglob counts yielded entries."""

    yields = 0

    def rglob(self, pattern):
        for entry in super().rglob(pattern):
            CountingPath.yields += 1
            yield entry
            CountingPath.yields += 1
            yield entry


def test_gather_is_lazy_and_caps_walked_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    for d in range(5):
        sub = root / f"dir_{d}"
        sub.mkdir()
        for f in range(100):
            (sub / f"note_{f:03d}.txt").write_text("lorem ipsum")
    total_entries = sum(1 for _ in root.rglob("*"))  # 505 (500 files + 5 dirs)

    CountingPath.yields = 0
    monkeypatch.setattr(recall, "Path", CountingPath)

    result = recall._gather_files([str(root)], max_files=20)

    assert len(result) == 20
    # Lazy cap: ~20 entries visited, NOT ~505. Old sorted() drained all.
    assert CountingPath.yields < total_entries // 2, (
        f"rglob yielded {CountingPath.yields} of {total_entries} entries "
        f"with max_files=20; expected lazy cap to stop near 20"
    )


def test_global_cap_across_dirs(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    for d in (dir_a, dir_b):
        sub = d / "inner"
        sub.mkdir(parents=True)
        for f in range(50):
            (sub / f"file_{f:03d}.txt").write_text("x")

    result = recall._gather_files([str(dir_a), str(dir_b)], max_files=20)

    # Global cap: 20 total across BOTH dirs, not 20 per dir.
    assert len(result) == 20
    # Every result lives under one of the two input dirs
    assert all(any(d in p.parents for d in (dir_a, dir_b)) for p in result)


def test_single_file_input_unchanged(tmp_path: Path) -> None:
    f_ok = tmp_path / "ok.txt"
    f_ok.write_text("hello")
    f_bad = tmp_path / "skip.exe"
    f_bad.write_text("mz")

    got_ok = recall._gather_files([str(f_ok)], max_files=20)
    got_bad = recall._gather_files([str(f_bad)], max_files=20)

    assert got_ok == [f_ok]
    assert got_bad == []
