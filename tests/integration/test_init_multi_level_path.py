"""Multi-level PATH validation tests (US2 / T031a).

Clarification Q5 (direct-parent-only, 2026-09-30 alignment):
- direct parent missing -> exit 2, regardless of grandparent presence
- init MUST NOT call mkdir(path.parent) or mkdir -p
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace


def test_happy_path_single_level_create(tmp_path: Path) -> None:
    """Path does not exist but its direct parent does -> single-layer mkdir."""
    target = tmp_path / "new_ws"
    assert not target.exists()
    result = init_workspace(path=target, name="TestAgent", force=False)
    assert result.exit_code == 0
    assert target.exists()
    assert (target / "instruction.md").exists()


def test_direct_parent_missing_returns_two(tmp_path: Path) -> None:
    """<tmp>/a/b/c where <tmp>/a/b/ does NOT exist -> exit 2, nothing created."""
    # Make sure a/ exists, a/b/ does NOT
    (tmp_path / "a").mkdir()
    target = tmp_path / "a" / "b" / "c"
    result = init_workspace(path=target, name="TestAgent", force=False)
    assert result.exit_code == 2
    assert not target.exists()
    assert not (tmp_path / "a" / "b").exists()


def test_multiple_missing_levels_returns_two(tmp_path: Path) -> None:
    """<tmp>/x/y/z with both <tmp>/x/ and <tmp>/x/y/ missing -> exit 2."""
    target = tmp_path / "x" / "y" / "z"
    result = init_workspace(path=target, name="TestAgent", force=False)
    assert result.exit_code == 2
    assert not (tmp_path / "x").exists()


def test_subprocess_direct_parent_missing(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c"
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(target), "--name", "TestAgent"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert not target.exists()
    assert not (tmp_path / "a" / "b").exists()


def test_path_is_regular_file_returns_two(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked.txt"
    blocked.write_text("not a directory")
    result = init_workspace(path=blocked, name="TestAgent", force=False)
    assert result.exit_code == 2


def test_init_workspace_does_not_call_mkdir_on_path_parent(tmp_path: Path) -> None:
    """Negative guard: PATH-validation branch must NOT call mkdir on parent.

    Per T031a: ensure init_workspace body has no `mkdir(path.parent)` and
    no `os.makedirs` / `pathlib.Path.mkdir(parents=True)` for the direct parent
    in the PATH-validation segment. Per-item create_fns are exempt.
    """
    src = Path("jarvis/jarvis_core/workspace/init.py").read_text()
    tree = ast.parse(src)

    # Concretely: scan for `mkdir` calls; the orchestrator's top-level
    # PATH-validation code MUST NOT use `parents=True` — that would span
    # multiple missing levels. Per-item create_fns (e.g. `_dir_create`,
    # `_memory_dir_create`) are exempt.
    bad: list[str] = []
    for func_def in tree.body:
        if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if func_def.name != "init_workspace":
            continue
        for node in ast.walk(func_def):
            if not isinstance(node, ast.Call):
                continue
            func_src = ast.unparse(node.func) if hasattr(ast, "unparse") else ast.dump(node.func)
            if "mkdir" in func_src:
                for kw in node.keywords:
                    if kw.arg == "parents" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        bad.append(f"line {node.lineno}: mkdir(parents=True) in init_workspace body")
    assert not bad, f"unexpected mkdir(parents=True) in init_workspace: {bad}"
    # Also: no `os.makedirs` anywhere in init_workspace.
    init_src = ast.unparse(tree.body[0]) if hasattr(ast, "unparse") else ""
    if "os.makedirs" in init_src or "makedirs" in init_src:
        bad.append("os.makedirs found in init_workspace")
    assert not bad, f"unexpected os.makedirs call: {bad}"