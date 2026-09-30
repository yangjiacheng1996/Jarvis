"""Unit tests for workspace templates (T014)."""

from __future__ import annotations

import json
import re

import pytest
import tomllib
import yaml

from jarvis.jarvis_core.workspace import templates


def test_instruction_md_template_basic() -> None:
    out = templates.INSTRUCTION_MD_TEMPLATE.format(
        NAME="TestAgent",
        TIMESTAMP="2026-09-29T00:00:00Z",
        PATH="/tmp/ws",
    )
    assert out.splitlines()[0] == "# TestAgent"
    assert "TestAgent" in out
    assert "2026-09-29T00:00:00Z" in out
    assert "/tmp/ws" in out
    assert len(out.encode("utf-8")) <= 4 * 1024, "NFR-003: instruction.md must be <= 4 KB"


def test_instruction_md_template_placeholders() -> None:
    """Spec FR-008: exactly 3 placeholders {NAME}, {TIMESTAMP}, {PATH}.

    {NAME} may appear multiple times (the spec allows it); {TIMESTAMP} and
    {PATH} each appear exactly once. No other .format placeholders remain.
    """
    text = templates.INSTRUCTION_MD_TEMPLATE
    assert text.count("{NAME}") >= 1
    assert text.count("{TIMESTAMP}") == 1
    assert text.count("{PATH}") == 1
    placeholders = set(re.findall(r"\{[A-Z_]+\}", text))
    assert placeholders == {"{NAME}", "{TIMESTAMP}", "{PATH}"}
    # No other braced tokens (like {DURATION})
    other = [tok for tok in placeholders if tok not in {"{NAME}", "{TIMESTAMP}", "{PATH}"}]
    assert other == []


def test_provider_toml_template() -> None:
    data = tomllib.loads(templates.PROVIDER_TOML_TEMPLATE)
    assert "provider" in data
    assert "extra" in data["provider"]
    extra = data["provider"]["extra"]
    assert extra["reasoning_effort"] in {"low", "medium", "high"}
    assert isinstance(extra["support_image"], bool)


def test_mcp_json_empty() -> None:
    data = json.loads(templates.MCP_JSON_EMPTY)
    assert "mcpServers" in data


@pytest.mark.parametrize("transport", ["http", "sse", "stdio"])
def test_mcp_readme_has_three_transport_snippets(transport: str) -> None:
    """US5 #2: each transport snippet must be json.loads()-able verbatim."""
    text = templates.MCP_README
    # Find each JSON block (```json ... ```)
    blocks = re.findall(r"```json\n(.*?)```", text, re.DOTALL)
    assert len(blocks) >= 3, f"expected at least 3 JSON blocks, got {len(blocks)}"
    # Each block must parse
    for block in blocks:
        json.loads(block)  # raises if invalid


def test_skills_example_md_frontmatter() -> None:
    """Agent Skills spec Level-1: only `name` + `description` (no `when_to_use`)."""
    text = templates.SKILLS_EXAMPLE_MD
    assert text.startswith("---")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    data = yaml.safe_load(parts[1])
    assert "name" in data
    assert "description" in data
    # Agent Skills Level-1 spec: `when_to_use` is NOT a valid field.
    # "When to use" semantics MUST be folded into `description`.
    assert "when_to_use" not in data, (
        "Agent Skills spec: frontmatter Level-1 must contain only `name` and `description`; "
        "fold usage hints into `description` instead of adding `when_to_use`."
    )
    # Exactly two top-level keys (or a small superset if you really must add metadata).
    assert set(data.keys()) == {"name", "description"}


def test_gitignore_contains_required_patterns() -> None:
    """Spec FR-013: required patterns must all be present."""
    g = templates.GITIGNORE
    required = [
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
    ]
    for pattern in required:
        assert pattern in g, f"GITIGNORE missing pattern: {pattern}"


def test_top_level_readme_warning_and_no_engine_names() -> None:
    r = templates.TOP_LEVEL_README
    assert "不要并发跑 `jarvis init`" in r
    for forbidden in ("LangGraph", "LangChain", "SqliteSaver", "MCPAdapter"):
        assert forbidden not in r, f"TOP_LEVEL_README must not contain {forbidden}"
    # Three required sections
    assert "可以改" in r
    assert "不要在这里新建" in r
    assert "需要帮助" in r


def test_mcp_readme_documented_transports() -> None:
    """US5 #2: README mentions http/sse/stdio."""
    r = templates.MCP_README
    assert "http" in r
    assert "sse" in r
    assert "stdio" in r


def test_memory_readme_checkpoint_and_store() -> None:
    """US5 #3: memory README distinguishes checkpoint vs store."""
    r = templates.MEMORY_README
    assert "checkpoint" in r
    assert "store" in r
    assert "checkpoint.sqlite3" in r
    assert "store.sqlite3" in r


# --- 2026-09-30 amendment content assertions ---------------------------------


def test_memory_readme_no_pre_amendment_wording(tmp_path_unit: str = None) -> None:
    """2026-09-30 (FR-021): MEMORY_README no longer claims store.sqlite3 is 'Core 阶段不生成'.

    The pre-amendment text "**当前 Core 阶段此文件不存在**，`jarvis init` 也不会创建它"
    was REMOVED per FR-021 because init now creates store.sqlite3 (FR-019).
    """
    r = templates.MEMORY_README
    assert "Core 阶段不生成" not in r
    assert "也不会创建" not in r or "init 阶段" in r  # rewording allowed
    # Positive assertion: the new wording (init 阶段幂等创建 / byte-level header check)
    assert "init 阶段" in r or "jarvis init" in r
    assert "存活检查" in r or "字节级" in r


def test_memory_readme_user_data_semantics() -> None:
    """2026-09-30 (Q6): MEMORY_README documents store.sqlite3 as user-data.

    `--force` never overwrites; corrupt → exit 7.
    """
    r = templates.MEMORY_README
    assert "user-data" in r or "用户数据" in r
    # --force never overwrites
    assert "--force" in r and ("永不" in r or "永远不" in r or "never" in r.lower() or "不会" in r)


def test_top_level_readme_scheduler_entry() -> None:
    """2026-09-30 (FR-021): TOP_LEVEL_README mentions scheduler/ as reserved directory."""
    r = templates.TOP_LEVEL_README
    assert "scheduler/" in r
    # Reserved-for-Scheduler wording
    assert "Scheduler" in r or "scheduler" in r


def test_top_level_readme_store_sqlite3_wording_updated() -> None:
    """2026-09-30 (FR-021): store.sqlite3 entry no longer says 'Core 阶段不生成'."""
    r = templates.TOP_LEVEL_README
    # Negative: pre-amendment phrasing is gone
    assert "Core 阶段不生成" not in r
    # Positive: new wording mentions init 创建 + Scheduler 写入
    assert "init" in r.lower()
    assert "Scheduler" in r or "scheduler" in r


def test_scheduler_readme_constant_exists_and_safe() -> None:
    """2026-09-30 (FR-020/FR-021): SCHEDULER_README constant exists with safe content."""
    assert hasattr(templates, "SCHEDULER_README"), "SCHEDULER_README constant must exist"
    r = templates.SCHEDULER_README
    assert r.strip(), "SCHEDULER_README must be non-empty"
    # FR-021: no engine-side terminology
    for forbidden in ("LangGraph", "LangChain", "SqliteSaver", "SqliteStore", "MCPAdapter"):
        assert forbidden not in r, f"SCHEDULER_README mentions forbidden term: {forbidden}"
    # It explains the reservation
    assert "Scheduler" in r or "scheduler" in r


def test_top_level_readme_no_engine_names_extended() -> None:
    """2026-09-30: TOP_LEVEL_README must not contain SqliteStore either (new term in MEMORY_README)."""
    r = templates.TOP_LEVEL_README
    for forbidden in ("LangGraph", "LangChain", "SqliteSaver", "SqliteStore", "MCPAdapter"):
        assert forbidden not in r, f"TOP_LEVEL_README mentions forbidden term: {forbidden}"