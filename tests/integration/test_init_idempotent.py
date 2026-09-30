"""Integration test for idempotent re-run (US2 / T029 + 2026-09-30 amendment).

Verification §2 (revised 2026-09-30): re-running jarvis init on a valid workspace is
a no-op. User data (including BOTH `checkpoint.sqlite3` AND `store.sqlite3` contents)
must be preserved byte-identically. After the 2026-09-30 amendment, store.sqlite3
is also a user-data item (is_user_data=True), so it MUST NOT be touched by re-runs
either.
"""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _snap(ws: Path) -> dict[str, str]:
    return {str(f.relative_to(ws)): _sha256(f) for f in sorted(ws.rglob("*")) if f.is_file()}


def test_idempotent_rerun_preserves_user_files(tmp_path: Path) -> None:
    # First init
    result1 = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", "TestAgent"],
        capture_output=True,
        text=True,
    )
    assert result1.returncode == 0, result1.stderr
    assert (tmp_path / "instruction.md").exists()

    # Mutate user files
    (tmp_path / "instruction.md").write_text(
        "# TestAgent\n\n我是 TestAgent\n\n## MyCustomSection\n\nCustom paragraph added by user.\n",
        encoding="utf-8",
    )

    # Inject a user row into checkpoint.sqlite3
    cp = tmp_path / "memory" / "checkpoint.sqlite3"
    conn = sqlite3.connect(str(cp))
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS user_sentinel (x INT)')
        conn.execute('INSERT INTO user_sentinel VALUES (42)')
        conn.commit()
    finally:
        conn.close()

    snap_before = _snap(tmp_path)

    # Re-run init via the library API (force=False)
    from jarvis.jarvis_core import init_workspace

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 0
    assert result.counts["created"] == 0
    # 2026-09-30: 18 ok (no `skipped` row anymore — store.sqlite3 is `ok` not `skipped`)
    assert result.counts["ok"] == 18, f"expected 18 ok, got {result.counts}"
    assert result.counts["skipped"] == 0

    snap_after = _snap(tmp_path)
    # All files byte-identical
    assert snap_before == snap_after, f"files changed: {snap_before ^ snap_after}"

    # Checkpoint size unchanged (NFR-001a + §7.3)
    size_after = cp.stat().st_size
    # The user row count is also preserved (because we never opened the file for write)
    conn = sqlite3.connect(str(cp))
    try:
        rows = conn.execute('SELECT count(*) FROM user_sentinel').fetchone()[0]
    finally:
        conn.close()
    assert rows == 1


def test_idempotent_recreate_only_deleted_item(tmp_path: Path) -> None:
    # First init
    from jarvis.jarvis_core import init_workspace

    init_workspace(path=tmp_path, name="TestAgent", force=False)
    snap_before = _snap(tmp_path)

    # Delete a single file
    target = tmp_path / "tools" / "__init__.py"
    target.unlink()

    # Re-run
    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 0
    assert result.counts["created"] == 1, f"expected 1 created, got {result.counts}"
    # 2026-09-30: 17 ok now (was 14; +store.sqlite3 ok, +scheduler/ ok, +scheduler/README.md ok = +3)
    assert result.counts["ok"] == 17, f"expected 17 ok, got {result.counts}"
    assert result.counts["skipped"] == 0

    # The deleted file is back, empty
    assert target.exists()
    assert target.read_text(encoding="utf-8") == ""

    snap_after = _snap(tmp_path)
    # The recreated file content is byte-identical to the original (both empty),
    # so the snapshots match. The key correctness assertion is:
    #   - the file is recreated (target.exists() is True)
    #   - the summary counts it under 'created'
    #   - all other files are byte-identical
    assert snap_before == snap_after