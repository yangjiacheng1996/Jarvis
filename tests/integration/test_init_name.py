"""Integration test for --name validation (US4 / T037 + T040).

Verifies:
- Spec FR-002: invalid --name -> exit 5, no files written.
- Spec Verification §6: --name "Bad/Name" -> exit 5; nothing created.
- US4 success path: --name "Alice_2" -> exit 0; title is "Alice_2".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_invalid_name_no_files_created(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", "Bad/Name"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 5
    # No files were created
    assert list(tmp_path.iterdir()) == [], f"unexpected files: {list(tmp_path.iterdir())}"
    # Stderr contains an error message
    assert "错误" in result.stderr or "错误" in result.stdout


def test_valid_name_with_underscore_digits(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", "Alice_2"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    instruction = (tmp_path / "instruction.md").read_text(encoding="utf-8")
    assert instruction.splitlines()[0] == "# Alice_2"


def test_valid_chinese_name(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", "中文-Agent+"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    instruction = (tmp_path / "instruction.md").read_text(encoding="utf-8")
    assert instruction.splitlines()[0] == "# 中文-Agent+"


@pytest.mark.parametrize(
    "bad_name",
    [
        "Alice;Bob",
        "name with space",
        "na|me",
        "name.with.dot",
    ],
)
def test_more_invalid_names(tmp_path: Path, bad_name: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", bad_name],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 5
    assert list(tmp_path.iterdir()) == []


def test_empty_name_via_hidden_path_returns_five(tmp_path: Path) -> None:
    """Q1 edge case: --name not given, but path basename is hidden filename
    -> derive_default_name returns '' -> exit 5.
    """
    target = tmp_path / ".gitignore"  # hidden filename
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(target)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 5
    # Nothing created
    assert not target.exists()