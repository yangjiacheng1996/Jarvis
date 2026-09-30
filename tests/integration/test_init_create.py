"""Integration test for first-time init (US1 / T015 + T028).

Verifies:
- Spec FR-001 (18-item registry + .gitignore side-effect; revised 2026-09-30)
- Spec FR-008 / FR-009 / FR-010 / FR-011 / FR-012 / FR-013
- Spec FR-018..FR-021 (2026-09-30 amendment: store.sqlite3 created by init; scheduler/ reserved)
- Spec NFR-005..NFR-007 (2026-09-30: no sqlite3.connect in check; no schema at init; round-trip create)
- Spec Verification §1

Drives the public library API: jarvis_core.init_workspace(...).
End-to-end CLI subprocess coverage lives in tests/integration/test_init_cli.py.
"""

from __future__ import annotations

import json
import sqlite3
import tomllib
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace


REQUIRED_ITEMS = (
    "instruction.md",
    "provider.toml",
    "tools",
    "tools/__init__.py",
    "tools/README.md",
    "mcp",
    "mcp/mcp.json",
    "mcp/README.md",
    "skills",
    "skills/README.md",
    "skills/example/SKILL.md",
    "memory",
    "memory/checkpoint.sqlite3",
    "memory/store.sqlite3",
    "memory/README.md",
    "scheduler",
    "scheduler/README.md",
    "README.md",
)


def test_first_time_init_creates_all_18_items(tmp_path: Path) -> None:
    """T015 (revised 2026-09-30): contract test — first-time init produces the full 18-item registry."""

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)

    # Library API contract (revised): len(items)==18, exit_code==0, counts per spec FR-001.
    assert len(result.items) == 18
    assert result.exit_code == 0
    assert result.counts == {
        "created": 18,
        "ok": 0,
        "warning": 0,
        "error": 0,
        "overwritten": 0,
        "skipped": 0,
    }
    assert result.name == "TestAgent"

    # All items in {created} on first run (no `skipped` rows post-amendment).
    states = {it.state for it in result.items}
    assert states.issubset({"created"})

    created_count = sum(1 for it in result.items if it.state == "created")
    skipped_count = sum(1 for it in result.items if it.state == "skipped")
    assert created_count == 18
    assert skipped_count == 0

    # All 18 items must exist on disk (incl. store.sqlite3 and scheduler/*)
    for rel in REQUIRED_ITEMS:
        assert (tmp_path / rel).exists(), f"missing: {rel}"


def test_first_time_init_content_assertions(tmp_path: Path) -> None:
    """T028 (revised 2026-09-30): full content sanity for first-time init (Verification §1)."""

    init_workspace(path=tmp_path, name="TestAgent", force=False)

    # instruction.md first line is `# TestAgent`
    instruction = (tmp_path / "instruction.md").read_text(encoding="utf-8")
    assert instruction.splitlines()[0] == "# TestAgent"

    # provider.toml parses via tomllib and has both [provider] and [provider.extra]
    data = tomllib.loads((tmp_path / "provider.toml").read_text(encoding="utf-8"))
    assert "provider" in data
    assert "extra" in data["provider"]

    # mcp/mcp.json parses via json with mcpServers key
    mcp_data = json.loads((tmp_path / "mcp/mcp.json").read_text(encoding="utf-8"))
    assert "mcpServers" in mcp_data

    # checkpoint.sqlite3 connects via sqlite3 with 0 business rows
    assert (tmp_path / "memory" / "checkpoint.sqlite3").exists()
    conn = sqlite3.connect(str(tmp_path / "memory" / "checkpoint.sqlite3"))
    try:
        rows = conn.execute("SELECT count(*) FROM checkpoints").fetchone()[0]
        assert rows == 0
    finally:
        conn.close()

    # FR-019 (revised 2026-09-30): store.sqlite3 EXISTS and is a valid empty SQLite
    assert (tmp_path / "memory" / "store.sqlite3").exists()
    header = (tmp_path / "memory" / "store.sqlite3").read_bytes()[:16]
    assert header == b"SQLite format 3\x00"
    # NFR-006: 0 tables (no schema at init)
    conn = sqlite3.connect(str(tmp_path / "memory" / "store.sqlite3"))
    try:
        n = conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
        assert n == 0, f"expected 0 tables in store.sqlite3, got {n}"
    finally:
        conn.close()

    # FR-020 (NEW 2026-09-30): scheduler/ + scheduler/README.md exist
    assert (tmp_path / "scheduler").is_dir()
    readme = (tmp_path / "scheduler" / "README.md")
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert text.strip(), "Scheduler README should be non-empty"
    # FR-021: README does not mention engine-side terminology
    for forbidden in ("LangGraph", "LangChain", "SqliteSaver", "SqliteStore", "MCPAdapter"):
        assert forbidden not in text, f"scheduler/README.md mentions {forbidden}"

    # .gitignore side-effect file
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "*.sqlite3" in gitignore
    assert "__pycache__/" in gitignore


def test_first_time_init_path_must_be_directory(tmp_path: Path) -> None:
    """Pre-condition: PATH must not be a regular file."""
    target = tmp_path / "blocked.txt"
    target.write_text("not a directory")
    result = init_workspace(path=target, name="Alice", force=False)
    assert result.exit_code == 2


def test_first_time_init_invalid_name(tmp_path: Path) -> None:
    """Spec FR-002: invalid --name -> exit 5, no items touched.

    The CLI validates --name at parse time; here we exercise the library's
    derive_default_name + validate_name chain via the orchestrator by
    passing a name that's empty (via path = hidden file).
    """
    # Path with a hidden filename -> derive_default_name returns "" -> exit 5
    hidden_path = tmp_path / ".gitignore"
    result = init_workspace(path=hidden_path, name=None, force=False)
    assert result.exit_code == 5
    # No items were processed
    assert len(result.items) == 0
    # Empty directory should remain
    assert hidden_path.exists() is False