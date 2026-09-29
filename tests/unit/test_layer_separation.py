"""Layer separation enforcement (T045 / N-03 / N-04 / N-05).

AST-scan jarvis/cli_client/**.py AND jarvis/__main__.py:
- Imports must be within {argparse, sys, pathlib, jarvis_core}.
AST-scan jarvis/jarvis_core/**/*.py:
- MUST NOT import argparse / click / typer / sys.argv / cli_client.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
JARVIS_ROOT = REPO_ROOT / "jarvis"

CLI_ALLOWED = {
    "argparse",
    "sys",
    "pathlib",
    "json",
    "re",
    "datetime",
    "typing",
    "dataclasses",
    "inspect",
    "collections",
    "__future__",
    "os",
    "functools",
    "importlib",
    "itertools",
    # jarvis / jarvis_core access
    "jarvis",
    "jarvis_core",
    # stdlib implicit / not flagged
    "io",
    "contextlib",
    "subprocess",
    "traceback",
    "logging",
    "tempfile",
    "shutil",
    "textwrap",
    "time",
    "urllib",
    "http",
}

CORE_FORBIDDEN = {
    "argparse",
    "click",
    "typer",
    "cli_client",
}


def _iter_py_files(root: Path):
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        yield p


def _imports_in_file(path: Path) -> set[str]:
    """Return the set of top-level module names imported by `path`.

    Relative imports (level >= 1) are resolved to the sibling module name and
    flagged only if they reach outside the current package boundary.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods: set[str] = set()
    # Detect the package containing this module (first parent that has __init__.py).
    pkg_parts: list[str] = []
    cur = path.parent
    while cur != cur.parent:
        if (cur / "__init__.py").exists():
            pkg_parts.insert(0, cur.name)
            cur = cur.parent
        else:
            break
    current_pkg = pkg_parts[0] if pkg_parts else ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top != current_pkg:
                    mods.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import. Resolve target package by going up.
                target_pkg = current_pkg
                if node.level > 1:
                    # level=2 -> root + 1 = package up one level
                    up = path.parent
                    for _ in range(node.level - 1):
                        up = up.parent
                    if (up / "__init__.py").exists():
                        target_pkg = up.name
                # If target_pkg is current_pkg or a sub-package, allow.
                # Otherwise, flag the target_pkg as a top-level import.
                if target_pkg != current_pkg:
                    mods.add(target_pkg)
            elif node.module:
                top = node.module.split(".")[0]
                if top != current_pkg:
                    mods.add(top)
    return mods


def test_cli_client_imports_only_allowed() -> None:
    cli_dir = JARVIS_ROOT / "cli_client"
    main_file = JARVIS_ROOT / "__main__.py"
    for p in list(_iter_py_files(cli_dir)) + [main_file]:
        imports = _imports_in_file(p)
        bad = imports - CLI_ALLOWED
        assert not bad, f"{p.relative_to(REPO_ROOT)} has disallowed imports: {bad}"


def test_cli_client_does_not_import_langgraph_or_langchain() -> None:
    """Constitution N-04: cli_client MUST NOT import langgraph/langchain/sqlite3 directly."""
    cli_dir = JARVIS_ROOT / "cli_client"
    main_file = JARVIS_ROOT / "__main__.py"
    forbidden_topics = {"langgraph", "langchain", "sqlite3", "tomllib"}
    for p in list(_iter_py_files(cli_dir)) + [main_file]:
        imports = _imports_in_file(p)
        bad = imports & forbidden_topics
        assert not bad, f"{p.relative_to(REPO_ROOT)} MUST NOT import: {bad}"


def test_jarvis_core_does_not_import_cli_frameworks() -> None:
    """Constitution N-05: jarvis_core MUST NOT import argparse/click/typer."""
    core_dir = JARVIS_ROOT / "jarvis_core"
    for p in _iter_py_files(core_dir):
        imports = _imports_in_file(p)
        bad = imports & CORE_FORBIDDEN
        assert not bad, f"{p.relative_to(REPO_ROOT)} MUST NOT import: {bad}"


def test_jarvis_core_does_not_import_any_client() -> None:
    """Constitution N-03: jarvis_core MUST NOT import any client module."""
    core_dir = JARVIS_ROOT / "jarvis_core"
    forbidden = {"cli_client", "web_client", "gui_client"}
    for p in _iter_py_files(core_dir):
        imports = _imports_in_file(p)
        bad = imports & forbidden
        assert not bad, f"{p.relative_to(REPO_ROOT)} MUST NOT import: {bad}"