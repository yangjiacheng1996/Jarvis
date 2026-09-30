"""CLI summary format test (T047 / Verification §14, revised 2026-09-30).

Per NFR-004:
- column-aligned table
- glyphs: + created, ✓ ok, ! warning, ✗ error, → overwritten, ⊘ skipped
- summary line: '<n> created · <n> ok · <n> warning · ... · <n> skipped'
- render_summary does NOT include the follow-up line (CLI adds it)
- CLI subprocess output DOES include the follow-up line on exit_code 0

Revised 2026-09-30: registry is 18 items (was 16); no `skipped` rows anymore
(store.sqlite3 is now `created` / `ok`, not `skipped`).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace, render_summary


_SUMMARY_RE = re.compile(
    r"^\d+ created · \d+ ok · \d+ warning · \d+ error · \d+ overwritten · \d+ skipped$",
    re.MULTILINE,
)


def test_render_summary_table_format(tmp_path: Path) -> None:
    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    output = render_summary(result)

    lines = output.split("\n")
    # First line is the header (first-run wording)
    assert "Workspace 'TestAgent'" in lines[0]
    # Each per-item row matches the pattern
    item_rows = [
        line
        for line in lines
        if line.startswith("  +")
        or line.startswith("  ✓")
        or line.startswith("  !")
        or line.startswith("  ✗")
        or line.startswith("  →")
        or line.startswith("  ⊘")
    ]
    assert len(item_rows) == 18, f"expected 18 item rows, got {len(item_rows)}"

    # The summary line at the bottom
    summary_line = lines[-1]
    assert _SUMMARY_RE.match(summary_line), f"summary line: {summary_line!r}"


def test_render_summary_does_not_include_followup(tmp_path: Path) -> None:
    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    output = render_summary(result)
    # Follow-up line must NOT be in render_summary output (T026 / spec L57)
    assert "已生成" not in output
    assert "jarvis run" not in output


def test_cli_subprocess_includes_followup_on_zero(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path), "--name", "TestAgent"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    out = result.stdout
    # Follow-up line appears at the end of stdout
    assert "已生成" in out
    assert "jarvis run" in out
    # Summary line is at the bottom
    assert _SUMMARY_RE.search(out), f"no summary line in: {out!r}"


def test_cli_subprocess_no_followup_on_nonzero(tmp_path: Path) -> None:
    """When exit_code != 0, the CLI does not print the follow-up line."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    (tmp_path / "provider.toml").write_text("garbage", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "jarvis", "init", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 6
    # Follow-up line is suppressed on non-zero exit
    assert "已生成" not in result.stdout