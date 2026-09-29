"""Unit tests for byte-level checkpoint header check (T023a / NFR-001a).

Verifies that check_checkpoint_sqlite_header:
- reads the first 16 bytes only;
- returns 'ok' iff bytes == b'SQLite format 3\\x00';
- NEVER calls sqlite3.connect() (monkeypatched counter).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jarvis.jarvis_core.workspace.items import check_checkpoint_sqlite_header


def _make_valid_sqlite(path: Path) -> None:
    """Create a valid sqlite file via SqliteSaver.setup()."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(path))
    try:
        SqliteSaver(conn).setup()
    finally:
        conn.close()


def test_valid_sqlite_file_returns_ok(tmp_path: Path) -> None:
    p = tmp_path / "cp.sqlite"
    _make_valid_sqlite(p)
    assert check_checkpoint_sqlite_header(p) == "ok"


def test_arbitrary_bytes_return_error(tmp_path: Path) -> None:
    p = tmp_path / "cp.sqlite"
    p.write_bytes(b"this is not a sqlite file at all!!")
    assert check_checkpoint_sqlite_header(p) == "error"


def test_empty_file_returns_error(tmp_path: Path) -> None:
    p = tmp_path / "cp.sqlite"
    p.write_bytes(b"")
    assert check_checkpoint_sqlite_header(p) == "error"


def test_short_file_returns_error(tmp_path: Path) -> None:
    p = tmp_path / "cp.sqlite"
    p.write_bytes(b"short")
    assert check_checkpoint_sqlite_header(p) == "error"


def test_missing_file_returns_error(tmp_path: Path) -> None:
    p = tmp_path / "cp.sqlite"
    assert check_checkpoint_sqlite_header(p) == "error"


def test_check_does_not_invoke_sqlite_connect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001a: byte-level check must not call sqlite3.connect()."""
    p = tmp_path / "ep.sqlite"
    p.write_bytes(b"anything here at all")
    counter = {"n": 0}
    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        counter["n"] += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting_connect)

    result = check_checkpoint_sqlite_header(p)
    assert result == "error"
    assert counter["n"] == 0, "sqlite3.connect must NOT be called in byte-level check"