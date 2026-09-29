"""Unit tests for validate_name and derive_default_name (T013)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.jarvis_core import derive_default_name, validate_name


@pytest.mark.parametrize(
    "name",
    ["Alice", "Alice_2", "中文-Agent+", "a", "X", "_", "+", "-", "abc123"],
)
def test_validate_name_accepts(name: str) -> None:
    assert validate_name(name) is True


@pytest.mark.parametrize(
    "name",
    ["", "Bad/Name", "with space", "Alice;Bob", "name.with.dot", "na|me", "na<me"],
)
def test_validate_name_rejects(name: str) -> None:
    assert validate_name(name) is False


@pytest.mark.parametrize(
    "path_str, expected",
    [
        ("/path/to/agent.git", "agent"),
        ("/path/to/report.md", "report"),
        ("/path/to/my.agent", "my"),
        ("/path/to/alice", "alice"),
        ("a/b/c", "c"),
        ("/path/to/no_extension", "no_extension"),
    ],
)
def test_derive_default_name_basic(path_str: str, expected: str) -> None:
    assert derive_default_name(Path(path_str)) == expected


@pytest.mark.parametrize(
    "path_str",
    [".gitignore", ".", "/"],
)
def test_derive_default_name_empty(path_str: str) -> None:
    """Q1 hidden-filename / single-char / root -> empty string."""
    assert derive_default_name(Path(path_str)) == ""