"""scheduler/ directory reservation (NEW 2026-09-30, FR-020 / D-08).

Verifies:
- After init, `<workspace>/scheduler/` exists as a directory
- `<workspace>/scheduler/README.md` exists as a non-empty file
- README does NOT contain engine-side terminology
- Idempotent re-run is byte-identical
- Regular-file conflict + --force recovers (mirrors `memory/` rule from Q3)
"""

from __future__ import annotations

from pathlib import Path

from jarvis.jarvis_core import init_workspace


def test_scheduler_dir_created_by_init(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    scheduler = tmp_path / "scheduler"
    assert scheduler.is_dir(), "FR-020: scheduler/ must be a directory after init"
    readme = scheduler / "README.md"
    assert readme.is_file(), "FR-020: scheduler/README.md must be a file after init"
    text = readme.read_text(encoding="utf-8")
    assert text.strip(), "scheduler/README.md must be non-empty"


def test_scheduler_readme_no_engine_terminology(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    text = (tmp_path / "scheduler" / "README.md").read_text(encoding="utf-8")
    for forbidden in ("LangGraph", "LangChain", "SqliteSaver", "SqliteStore", "MCPAdapter"):
        assert forbidden not in text, f"scheduler/README.md mentions forbidden term: {forbidden}"


def test_scheduler_dir_byte_identical_on_rerun(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    before = (tmp_path / "scheduler" / "README.md").read_bytes()

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    after = (tmp_path / "scheduler" / "README.md").read_bytes()
    assert before == after, "scheduler/README.md must not change on re-run"

    sched = next(it for it in result.items if it.name == "scheduler")
    readme_item = next(it for it in result.items if it.name == "scheduler/README.md")
    assert sched.state == "ok"
    assert readme_item.state == "ok"


def test_scheduler_dir_readme_missing_recreated(tmp_path: Path) -> None:
    """If user deleted scheduler/README.md, init recreates it."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    (tmp_path / "scheduler" / "README.md").unlink()

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert (tmp_path / "scheduler" / "README.md").is_file()

    readme_item = next(it for it in result.items if it.name == "scheduler/README.md")
    assert readme_item.state == "created"


def test_scheduler_dir_regular_file_conflict_no_force(tmp_path: Path) -> None:
    """scheduler/ as a regular file + no --force → exit 6, file untouched."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    # Replace scheduler/ with a regular file
    import shutil
    shutil.rmtree(tmp_path / "scheduler")
    (tmp_path / "scheduler").write_text("not a directory", encoding="utf-8")

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert result.exit_code == 6, f"expected 6, got {result.exit_code}"
    # File is still the regular file (untouched)
    assert (tmp_path / "scheduler").is_file()
    assert (tmp_path / "scheduler").read_text(encoding="utf-8") == "not a directory"


def test_scheduler_dir_regular_file_conflict_with_force(tmp_path: Path) -> None:
    """scheduler/ as a regular file + --force → exit 0, dir + README recreated."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    import shutil
    shutil.rmtree(tmp_path / "scheduler")
    (tmp_path / "scheduler").write_text("not a directory", encoding="utf-8")

    result = init_workspace(path=tmp_path, name="TestAgent", force=True)
    assert result.exit_code == 0, f"expected 0, got {result.exit_code}"
    assert (tmp_path / "scheduler").is_dir()
    assert (tmp_path / "scheduler" / "README.md").is_file()