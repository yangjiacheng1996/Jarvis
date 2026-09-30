"""store.sqlite3 is now provisioned by init (FR-019 / Verification §8, revised 2026-09-30).

This test file replaces the pre-amendment `test_init_store_skipped.py`. The behavior
under test:

- First init: store.sqlite3 is created as an empty valid SQLite file (no schema per NFR-006);
  state is `created`, not `skipped`.
- Re-run with valid header: state is `ok`, detail "存活检查通过".
- Re-run with corrupted file (truncated) → exit code 6 (no --force) or 7 (with --force);
  file is **NOT** overwritten even with `--force` because store.sqlite3 is now
  `is_user_data=True` (Q6).
- `sqlite3.connect()` is NOT called during the liveness check (NFR-005).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jarvis.jarvis_core import init_workspace


def test_store_sqlite3_created_by_init(tmp_path: Path) -> None:
    """FR-019: store.sqlite3 EXISTS after first init (was absent pre-amendment)."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    store = tmp_path / "memory" / "store.sqlite3"
    assert store.exists(), "FR-019: store.sqlite3 must be created by init"
    # Header magic check (NFR-005)
    assert store.read_bytes()[:16] == b"SQLite format 3\x00"
    # NFR-006: 0 tables (no schema at init)
    conn = sqlite3.connect(str(store))
    try:
        n = conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
        assert n == 0, f"expected 0 tables, got {n}"
    finally:
        conn.close()


def test_store_sqlite3_byte_identical_on_rerun(tmp_path: Path) -> None:
    """FR-019 / NFR-005: re-run only does byte-level header check; file is byte-identical."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    store = tmp_path / "memory" / "store.sqlite3"
    before = store.read_bytes()

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)

    after = store.read_bytes()
    assert before == after, "store.sqlite3 must not be modified on idempotent re-run"

    # State: ok (not skipped, not created)
    store_item = next(it for it in result.items if it.name == "memory/store.sqlite3")
    assert store_item.state == "ok", f"expected 'ok', got {store_item.state}"
    assert "存活检查通过" in (store_item.detail or "")


def test_store_sqlite3_force_does_not_overwrite(tmp_path: Path) -> None:
    """Q6 (revised): --force does NOT overwrite store.sqlite3 (it is user-data)."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    store = tmp_path / "memory" / "store.sqlite3"

    # Corrupt provider.toml to force the --force path
    (tmp_path / "provider.toml").write_text("garbage", encoding="utf-8")
    before = store.read_bytes()
    init_workspace(path=tmp_path, name="TestAgent", force=True)
    after = store.read_bytes()
    assert before == after, "store.sqlite3 must NOT be overwritten by --force (Q6)"


def test_store_sqlite3_corrupt_with_force_returns_seven(tmp_path: Path) -> None:
    """Q6 (revised): corrupt store.sqlite3 + --force → exit 7, file untouched."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    store = tmp_path / "memory" / "store.sqlite3"

    # Truncate to corrupt the header
    store.write_bytes(b"")
    assert store.read_bytes() == b""

    result = init_workspace(path=tmp_path, name="TestAgent", force=True)
    assert result.exit_code == 7, f"expected 7, got {result.exit_code}"

    # File is STILL empty (--force did NOT overwrite)
    assert store.read_bytes() == b"", "store.sqlite3 must NOT be overwritten by --force (Q6)"


def test_store_sqlite3_corrupt_without_force_returns_six(tmp_path: Path) -> None:
    """Q6 (revised): corrupt store.sqlite3 + no --force → exit 6."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    store = tmp_path / "memory" / "store.sqlite3"

    # Truncate to corrupt the header
    store.write_bytes(b"")

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 6, f"expected 6, got {result.exit_code}"

    # File is STILL empty (no --force, no overwrite)
    assert store.read_bytes() == b""


def test_store_sqlite3_liveness_check_no_sqlite_connect(tmp_path: Path) -> None:
    """NFR-005: sqlite3.connect() is NOT called during the liveness check on store.sqlite3."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    # Monkeypatch sqlite3.connect to count calls during the re-run.
    # The re-run should NOT call connect on store.sqlite3 (only on checkpoint.sqlite3
    # if anything — actually no, neither check path calls sqlite3.connect).
    counter = {"n": 0}
    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        counter["n"] += 1
        return real_connect(*args, **kwargs)

    import unittest.mock as mock
    with mock.patch.object(sqlite3, "connect", side_effect=counting_connect):
        result = init_workspace(path=tmp_path, name="TestAgent", force=False)

    # The re-run path: NO sqlite3.connect() calls (NFR-001a + NFR-005).
    # (We can't distinguish checkpoint vs store calls in the counter, but the TOTAL
    #  should be 0 since neither check path calls connect.)
    assert counter["n"] == 0, f"NFR-005 violation: sqlite3.connect called {counter['n']} times during re-run"
    assert result.exit_code == 0