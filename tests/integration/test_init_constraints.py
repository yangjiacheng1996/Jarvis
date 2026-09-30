"""Workspace constraint enforcement (T046 / Verification §9).

Forbids (per constitution N-01, N-02, D-04):
  agent.py / main.py / subagent / middleware / connectors / channels /
  schedules / evals / identity / memory.py / sandbox + any mcp/*.py.

Also verifies FR-016: init MUST NOT run git init (no .git/ created).
Also verifies FR-013: .gitignore contains all required patterns.
Also verifies FR-001: .gitignore is NOT counted in InitResult.items.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.jarvis_core import init_workspace


def test_no_forbidden_python_entries(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    forbidden_top_level = [
        "agent.py",
        "main.py",
        "subagent",
        "middleware",
        "connectors",
        "channels",
        "schedules",
        "evals",
        "identity",
        "memory.py",
        "sandbox",
    ]
    for name in forbidden_top_level:
        assert not (tmp_path / name).exists(), f"forbidden entry: {name}"


def test_no_python_files_in_mcp(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    mcp_dir = tmp_path / "mcp"
    assert mcp_dir.is_dir()
    py_files = list(mcp_dir.glob("*.py"))
    assert py_files == [], f"mcp/ must NOT contain .py files, got: {py_files}"


def test_no_git_directory_created(tmp_path: Path) -> None:
    """FR-016: init MUST NOT run git init."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    assert not (tmp_path / ".git").exists()


def test_gitignore_contains_required_patterns(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    g = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    for pattern in [
        "*.sqlite3",
        "*.sqlite3-journal",
        "*.sqlite3-wal",
        "*.sqlite3-shm",
        "__pycache__/",
        "*.py[cod]",
        "*$py.class",
        ".env",
        ".venv/",
        "venv/",
        "env/",
    ]:
        assert pattern in g, f"gitignore missing pattern: {pattern}"


def test_gitignore_is_not_in_items_registry(tmp_path: Path) -> None:
    """Spec FR-001: .gitignore is a side-effect file; NOT counted in items.

    Revised 2026-09-30: registry is 18 items (was 16); the assertion is updated
    accordingly. `scheduler/` + `scheduler/README.md` are NEW items in the registry;
    `.gitignore` remains a side-effect file (NOT in items).
    """
    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    item_names = {it.name for it in result.items}
    assert ".gitignore" not in item_names
    assert len(result.items) == 18