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
    text = templates.SKILLS_EXAMPLE_MD
    assert text.startswith("---")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    data = yaml.safe_load(parts[1])
    assert "name" in data
    assert "description" in data
    assert "when_to_use" in data


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