"""Integration test for --force recovery (US3 / T032).

Verifies:
- Spec FR-003 (force only reverts error items, never user data)
- Spec Verification §4 (broken provider.toml + no --force -> exit 6)
- Spec Verification §5 (broken provider.toml + --force -> exit 0, file restored)
- memory/checkpoint.sqlite3 is byte-identical across both runs (NFR-001a)
"""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib

from jarvis.jarvis_core import init_workspace


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_broken_provider_no_force_returns_six(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    cp_sha_before = _sha256(tmp_path / "memory" / "checkpoint.sqlite3")

    (tmp_path / "provider.toml").write_text("this is not valid toml ====", encoding="utf-8")
    sha_before = _sha256(tmp_path / "provider.toml")

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 6
    # File is byte-identical to the corrupted version
    assert _sha256(tmp_path / "provider.toml") == sha_before

    # checkpoint.sqlite3 is byte-identical across this run
    assert _sha256(tmp_path / "memory" / "checkpoint.sqlite3") == cp_sha_before


def test_broken_provider_with_force_returns_zero_and_restores(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    cp_sha_before = _sha256(tmp_path / "memory" / "checkpoint.sqlite3")

    (tmp_path / "provider.toml").write_text("this is not valid toml ====", encoding="utf-8")

    result = init_workspace(path=tmp_path, name="TestAgent", force=True)
    assert result.exit_code == 0
    # File parses again
    data = tomllib.loads((tmp_path / "provider.toml").read_text(encoding="utf-8"))
    assert "provider" in data
    assert "extra" in data["provider"]
    # Counts show overwritten
    assert result.counts["overwritten"] == 1
    assert result.counts["error"] == 0

    # checkpoint.sqlite3 byte-identical
    assert _sha256(tmp_path / "memory" / "checkpoint.sqlite3") == cp_sha_before


def test_force_via_subprocess(tmp_path: Path) -> None:
    """CLI subprocess: jarvis init . --force restores broken provider.toml."""
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", "TestAgent"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    (tmp_path / "provider.toml").write_text("garbage", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--force"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "→ provider.toml" in result.stdout
    # Verify file is valid TOML
    data = tomllib.loads((tmp_path / "provider.toml").read_text(encoding="utf-8"))
    assert "provider" in data


def test_force_does_not_overwrite_user_data(tmp_path: Path) -> None:
    """FR-003 + US3 acceptance #3: --force MUST NOT overwrite checkpoint.sqlite3."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    cp = tmp_path / "memory" / "checkpoint.sqlite3"
    # Inject a user row
    conn = sqlite3.connect(str(cp))
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS user_sentinel (x INT)')
        conn.execute('INSERT INTO user_sentinel VALUES (1)')
        conn.commit()
    finally:
        conn.close()

    bytes_before = cp.stat().st_size

    # Corrupt provider.toml AND truncate checkpoint.sqlite3 (so it returns 'error')
    (tmp_path / "provider.toml").write_text("garbage ====", encoding="utf-8")
    cp.write_bytes(b"")  # truncate to 0 bytes -> header check fails

    result = init_workspace(path=tmp_path, name="TestAgent", force=True)
    # Exit code must be 7: checkpoint.sqlite3 is user data; --force does not repair.
    assert result.exit_code == 7

    # checkpoint.sqlite3 is still 0 bytes (NOT overwritten)
    assert cp.stat().st_size == 0

    # provider.toml is restored
    data = tomllib.loads((tmp_path / "provider.toml").read_text(encoding="utf-8"))
    assert "provider" in data


def test_force_does_not_delete_user_rows_in_checkpoint(tmp_path: Path) -> None:
    """Even without breaking the file, --force must not touch checkpoint.sqlite3."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    cp = tmp_path / "memory" / "checkpoint.sqlite3"
    conn = sqlite3.connect(str(cp))
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS user_sentinel (x INT)')
        conn.execute('INSERT INTO user_sentinel VALUES (1)')
        conn.commit()
    finally:
        conn.close()

    # Re-open to count rows (the previous connection is closed)
    conn = sqlite3.connect(str(cp))
    try:
        rows_before = conn.execute('SELECT count(*) FROM user_sentinel').fetchone()[0]
    finally:
        conn.close()
    bytes_before = cp.stat().st_size

    # Re-run with --force; nothing to repair, but ensure checkpoint untouched.
    result = init_workspace(path=tmp_path, name="TestAgent", force=True)
    assert result.exit_code == 0

    assert cp.stat().st_size == bytes_before
    conn = sqlite3.connect(str(cp))
    try:
        rows_after = conn.execute('SELECT count(*) FROM user_sentinel').fetchone()[0]
    finally:
        conn.close()
    assert rows_after == rows_before