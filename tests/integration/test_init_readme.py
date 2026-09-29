"""Integration test for README usability (US5 / T041).

Verifies:
- Spec US5 acceptance #1: top-level README contains 3 sections + concurrent warning.
- Spec US5 acceptance #2: mcp/README.md has 3 transport snippets.
- Spec US5 acceptance #3: memory/README.md distinguishes checkpoint vs store.
- Constitution §8: NO engine framework names (LangGraph/LangChain/SqliteSaver/MCPAdapter)
  in the top-level README.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.jarvis_core import init_workspace


def test_top_level_readme_three_sections_and_warning(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    r = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "可以改" in r
    assert "不要在这里新建" in r
    assert "需要帮助" in r
    # Concurrent warning (Q4)
    assert "不要并发跑 `jarvis init`" in r


def test_top_level_readme_no_engine_names(tmp_path: Path) -> None:
    """Constitution §8: top-level README must not expose engine framework names."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    r = (tmp_path / "README.md").read_text(encoding="utf-8")
    for forbidden in ("LangGraph", "LangChain", "SqliteSaver", "MCPAdapter"):
        assert forbidden not in r, f"README must not contain {forbidden}"


def test_top_level_readme_lists_editable_items(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    r = (tmp_path / "README.md").read_text(encoding="utf-8")
    # Editable items listed
    for item in [
        "instruction.md",
        "provider.toml",
        "mcp/mcp.json",
        "memory/checkpoint.sqlite3",
        "memory/store.sqlite3",
    ]:
        assert item in r, f"README must list editable item: {item}"


def test_top_level_readme_lists_forbidden_items(tmp_path: Path) -> None:
    """Constitution N-01 / N-02 / D-04 forbidden list."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    r = (tmp_path / "README.md").read_text(encoding="utf-8")
    # Mention the forbidden concepts
    assert "agent.py" in r or "Python 入口" in r
    assert "subagent" in r or "子智能体" in r


def test_mcp_readme_three_transports(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    r = (tmp_path / "mcp" / "README.md").read_text(encoding="utf-8")
    assert "http" in r
    assert "sse" in r
    assert "stdio" in r
    # The README mentions all three example types in JSON-form
    assert "transport" in r


def test_memory_readme_distinguishes_checkpoint_and_store(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    r = (tmp_path / "memory" / "README.md").read_text(encoding="utf-8")
    assert "checkpoint" in r.lower() or "Checkpoint" in r
    assert "store" in r.lower() or "Store" in r
    # The README mentions checkpoint.sqlite3 explicitly
    assert "checkpoint.sqlite3" in r
    assert "store.sqlite3" in r


def test_tools_readme_mentions_docstring_convention(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    r = (tmp_path / "tools" / "README.md").read_text(encoding="utf-8")
    # Docstring / JSON Schema convention
    assert "docstring" in r.lower() or "Docstring" in r