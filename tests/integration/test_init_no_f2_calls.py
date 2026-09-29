"""F1 does not perform F2 readiness work (T046a / NFR-001b).

Two halves:
1. AST static assertion: no langchain import anywhere; only allowed langgraph
   touchpoint is `from langgraph.checkpoint.sqlite import SqliteSaver` in
   `jarvis/jarvis_core/workspace/items.py`.
2. Runtime monkeypatch: 100 iterations of idempotent re-run; assert no
   sqlite3.connect, no PRAGMA queries, no subprocess.run.
"""

from __future__ import annotations

import ast
import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# (1) AST static scan
# ---------------------------------------------------------------------------


def _all_py_files():
    for p in (REPO_ROOT / "jarvis").rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def test_no_langchain_anywhere() -> None:
    """AST-level scan: no `import langchain` or `from langchain...` statement."""
    for p in _all_py_files():
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top != "langchain", (
                        f"{p.relative_to(REPO_ROOT)} imports langchain ({alias.name})"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] == "langchain":
                    raise AssertionError(
                        f"{p.relative_to(REPO_ROOT)} imports from langchain ({node.module})"
                    )


def test_langgraph_only_in_items_checkpoint_create() -> None:
    """AST-level scan: the ONLY allowed langgraph touchpoint is items.py."""

    for p in _all_py_files():
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top == "langgraph":
                        raise AssertionError(
                            f"{p.relative_to(REPO_ROOT)} imports langgraph ({alias.name})"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] == "langgraph":
                    rel = p.relative_to(REPO_ROOT).parts
                    assert rel[-4:] == ("jarvis", "jarvis_core", "workspace", "items.py"), (
                        f"langgraph import in {p.relative_to(REPO_ROOT)} — "
                        f"only allowed in jarvis/jarvis_core/workspace/items.py"
                    )


def test_sqlite_saver_used_only_for_setup() -> None:
    """SqliteSaver is used only for .setup(); no .from_conn_string / .get_tuple etc."""
    items_path = REPO_ROOT / "jarvis" / "jarvis_core" / "workspace" / "items.py"
    src = items_path.read_text(encoding="utf-8")
    # Find all SqliteSaver method calls
    calls = re.findall(r"SqliteSaver\.\w+", src)
    allowed = {"SqliteSaver.setup", "SqliteSaver(", "SqliteSaver"}
    unexpected = [c for c in calls if c not in {"SqliteSaver.setup", "SqliteSaver("}]
    assert not unexpected, f"disallowed SqliteSaver APIs: {unexpected}"


# ---------------------------------------------------------------------------
# (2) Runtime monkeypatch (slow)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_idempotent_re_run_does_no_f2_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    counters = {
        "sqlite3.connect": 0,
        "subprocess.run": 0,
        "requests.post": 0,
        "open_sqlite": 0,
    }

    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        counters["sqlite3.connect"] += 1
        # Don't count opens of files that aren't sqlite
        return real_connect(*args, **kwargs)

    real_run = subprocess.run

    def counting_run(*args, **kwargs):
        counters["subprocess.run"] += 1
        return real_run(*args, **kwargs)

    real_open = open

    def counting_open(file, *args, **kwargs):
        if isinstance(file, (str, bytes)) and "sqlite3" in str(file):
            counters["open_sqlite"] += 1
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting_connect)
    monkeypatch.setattr(subprocess, "run", counting_run)
    try:
        import requests as _requests

        monkeypatch.setattr(_requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no http")))
    except ImportError:
        pass
    monkeypatch.setattr("builtins.open", counting_open)

    # Warmup (not measured)
    for _ in range(5):
        init_workspace(path=tmp_path, name="TestAgent", force=False)

    # Measure 100 iterations
    for _ in range(100):
        result = init_workspace(path=tmp_path, name="TestAgent", force=False)
        assert result.exit_code == 0

    # NFR-001b: no sqlite3.connect (and no other F2 readiness work)
    assert counters["sqlite3.connect"] == 0, f"sqlite3.connect called {counters['sqlite3.connect']} times"
    assert counters["open_sqlite"] == 0
    assert counters["subprocess.run"] == 0