"""Integration test for memory/ regular-file conflict recovery (US3 / T033).

Clarification Q3:
- Without --force: regular file in place of memory/ -> error, file unchanged, exit 6.
- With --force: remove conflicting file, mkdir memory/, then standard
  checkpoint.sqlite3 create flow.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace


def test_memory_as_regular_file_no_force_returns_six(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    # Replace memory/ with a regular file
    import shutil

    shutil.rmtree(tmp_path / "memory")
    (tmp_path / "memory").write_text("I am a regular file", encoding="utf-8")
    sha_before = (tmp_path / "memory").read_bytes()

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 6
    # The regular file is byte-identical (untouched)
    assert (tmp_path / "memory").read_bytes() == sha_before


def test_memory_as_regular_file_with_force_returns_zero(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    import shutil

    shutil.rmtree(tmp_path / "memory")
    (tmp_path / "memory").write_text("I am a regular file", encoding="utf-8")

    result = init_workspace(path=tmp_path, name="TestAgent", force=True)
    assert result.exit_code == 0

    # memory/ is now a directory
    assert (tmp_path / "memory").is_dir()
    # checkpoint.sqlite3 is recreated via standard flow
    assert (tmp_path / "memory" / "checkpoint.sqlite3").exists()
    conn = sqlite3.connect(str(tmp_path / "memory" / "checkpoint.sqlite3"))
    try:
        rows = conn.execute("SELECT count(*) FROM checkpoints").fetchone()[0]
        assert rows == 0
    finally:
        conn.close()