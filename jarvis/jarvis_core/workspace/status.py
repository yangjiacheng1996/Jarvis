"""Item status enum and exit-code rules for jarvis init (T003).

Per contracts/item-status.md: precedence order for compute_exit_code.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


ItemState = Literal["created", "ok", "warning", "error", "overwritten", "skipped"]


@dataclass(frozen=True)
class ItemStatus:
    """Per-item outcome reported by jarvis_core (T003 / contracts/library-api.md)."""

    path: str
    name: str
    state: ItemState
    detail: str | None = None


@dataclass
class InitResult:
    """Aggregate outcome of one init_workspace(...) call (T003)."""

    path: Path
    name: str
    items: list[ItemStatus] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    exit_code: int = 0


def compute_exit_code(
    items: Iterable[ItemStatus],
    force: bool,
    pre_condition_code: int = 0,
    sqlite_setup_failed: bool = False,
) -> int:
    """Compute the final exit code per contracts/item-status.md (T003).

    Precedence (binding order):
    1. pre_condition_code in {2, 5} -> return as-is.
    2. sqlite_setup_failed=True -> 4 (takes precedence over any item errors).
    3. Any item error AND force=True -> 7 (--force attempt still failed).
    4. Any item error AND force=False -> 6.
    5. All items in {created, ok, overwritten, skipped, warning} -> 0.

    Note: warning does NOT contribute to non-zero (spec FR-007).
    Code 1 is produced by cli_client/jarvis_cli.py top-level try/except, NOT here.
    """

    pre_condition_code = pre_condition_code or 0
    if pre_condition_code in (2, 5):
        return pre_condition_code
    if sqlite_setup_failed:
        return 4
    states = [it.state for it in items]
    has_error = any(s == "error" for s in states)
    if has_error:
        return 7 if force else 6
    return 0


def count_items(items: Iterable[ItemStatus]) -> dict[str, int]:
    """Aggregate counts from a list of ItemStatus (T025 wiring)."""
    counts = Counter(it.state for it in items)
    out: dict[str, int] = {}
    for k in ("created", "ok", "warning", "error", "overwritten", "skipped"):
        out[k] = int(counts.get(k, 0))
    return out