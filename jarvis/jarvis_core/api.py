"""jarvis_core public API surface (T008 + T026).

The library exposes:
    - init_workspace(path, name, force) -> InitResult
    - render_summary(result) -> str
    - validate_name, derive_default_name
    - ItemStatus, InitResult, ItemState

Per contracts/library-api.md.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# Re-export types
from .workspace.status import (
    InitResult as _InitResult,
    ItemStatus as _ItemStatus,
    ItemState,
    compute_exit_code,
    count_items,
)
from .workspace.name import validate_name, derive_default_name
from .workspace.init import init_workspace, SqliteSetupError


# Public type aliases
ItemStatus = _ItemStatus
InitResult = _InitResult


# Glyph map per contracts/cli.md
_GLYPHS: dict[str, str] = {
    "created": "+",
    "ok": "✓",
    "warning": "!",
    "error": "✗",
    "overwritten": "→",
    "skipped": "⊘",
}

_STATE_WORDS: dict[str, str] = {
    "created": "created",
    "ok": "ok",
    "warning": "warning",
    "error": "error",
    "overwritten": "overwritten",
    "skipped": "skipped",
}

# Canonical order per FR-005 / NFR-004
_BUCKET_ORDER = ("created", "ok", "warning", "error", "overwritten", "skipped")


def render_summary(result: InitResult) -> str:
    """Render InitResult to the CLI summary table format described in contracts/cli.md.

    Does NOT include the trailing exit-code-aware follow-up line; that is added
    by the CLI (per contracts/library-api.md L57).

    Output does NOT end with a trailing newline (CLI adds it).
    No ANSI color codes.
    """

    counts = result.counts or {}
    any_created = counts.get("created", 0) > 0

    lines: list[str] = []
    if any_created:
        lines.append(f"Workspace '{result.name}' at {result.path}")
    else:
        lines.append(f"Workspace at {result.path}（已存在，按幂等流程处理）")
    lines.append("")  # blank line

    # Per-item table
    name_width = 30
    for it in result.items:
        glyph = _GLYPHS.get(it.state, "?")
        display = it.name  # always show the full relpath
        padded = display.ljust(name_width)
        state_word = _STATE_WORDS.get(it.state, it.state)
        row = f"  {glyph} {padded} {state_word}"
        if it.detail:
            row += f" ({it.detail})"
        lines.append(row)

    lines.append("")  # blank line

    # Summary line — 6 buckets, canonical order
    parts = [f"{counts.get(b, 0)} {b}" for b in _BUCKET_ORDER]
    lines.append(" · ".join(parts))

    return "\n".join(lines)


__all__ = [
    "InitResult",
    "ItemState",
    "ItemStatus",
    "SqliteSetupError",
    "compute_exit_code",
    "count_items",
    "derive_default_name",
    "init_workspace",
    "render_summary",
    "validate_name",
]