"""Recreate-missing-item integration test (US2 / T031)."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_recreate_only_deleted_init_py(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    snap_before = {
        str(f.relative_to(tmp_path)): _sha256(f)
        for f in sorted(tmp_path.rglob("*"))
        if f.is_file()
    }

    # User accidentally deletes tools/__init__.py
    target = tmp_path / "tools" / "__init__.py"
    target.unlink()

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 0
    assert result.counts["created"] == 1
    assert result.counts["ok"] == 14
    assert result.counts["skipped"] == 1

    snap_after = {
        str(f.relative_to(tmp_path)): _sha256(f)
        for f in sorted(tmp_path.rglob("*"))
        if f.is_file()
    }

    # The recreated file content is byte-identical to the original (both empty),
    # so the snapshots match. The key correctness assertion is:
    #   - the file is recreated (target.exists() is True)
    #   - the summary counts it under 'created'
    #   - all other files are byte-identical
    assert snap_before == snap_after

    # The recreated file is empty
    assert target.read_text(encoding="utf-8") == ""


def test_recreate_via_subprocess(tmp_path: Path) -> None:
    """T031 (alternate path): the CLI subprocess also recreates the missing file."""
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", "TestAgent"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    target = tmp_path / "tools" / "__init__.py"
    target.unlink()

    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "+ tools/__init__.py" in result.stdout
    assert target.exists()