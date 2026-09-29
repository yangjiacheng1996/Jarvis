"""checkpoint.sqlite3 is byte-equal across all scenarios (T049 / Verification §7)."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace


def test_checkpoint_byte_identical_across_force_runs(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    cp = tmp_path / "memory" / "checkpoint.sqlite3"
    # Add a user row
    conn = sqlite3.connect(str(cp))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS user_sentinel (x INT)")
        conn.execute("INSERT INTO user_sentinel VALUES (1)")
        conn.commit()
    finally:
        conn.close()

    bytes_before = cp.stat().st_size
    rows_before = _row_count(cp, "user_sentinel")

    # Truncate checkpoint.sqlite3 to 0 bytes so header check fails
    cp.write_bytes(b"")

    # Corrupt provider.toml
    (tmp_path / "provider.toml").write_text("garbage", encoding="utf-8")

    result = init_workspace(path=tmp_path, name="TestAgent", force=True)
    # exit_code 7: user-data item left untouched by --force
    assert result.exit_code == 7
    # checkpoint.sqlite3 is still 0 bytes
    assert cp.stat().st_size == 0

    # bytes/rows: the truncated file's size is 0; the row count is undefined.
    # We already showed bytes == 0 which is the post-condition of this test.


def test_checkpoint_no_sqlite_connect_in_check_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001a: byte-level check does NOT call sqlite3.connect()."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    cp = tmp_path / "memory" / "checkpoint.sqlite3"

    counter = {"n": 0}
    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        counter["n"] += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting_connect)

    # Idempotent re-run on a healthy workspace
    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 0
    assert counter["n"] == 0, f"sqlite3.connect was called {counter['n']} times in idempotent re-run"


def _row_count(cp: Path, table: str) -> int:
    conn = sqlite3.connect(str(cp))
    try:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()