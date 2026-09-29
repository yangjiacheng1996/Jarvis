"""Unit tests for compute_exit_code (T012, T012b, T012c)."""

from __future__ import annotations

from jarvis.jarvis_core import ItemStatus
from jarvis.jarvis_core.workspace.status import compute_exit_code


def _ok(name: str) -> ItemStatus:
    return ItemStatus(path=name, name=name, state="ok")


def _created(name: str) -> ItemStatus:
    return ItemStatus(path=name, name=name, state="created")


def _warning(name: str) -> ItemStatus:
    return ItemStatus(path=name, name=name, state="warning", detail="soft")


def _error(name: str) -> ItemStatus:
    return ItemStatus(path=name, name=name, state="error", detail="hard")


def _skipped(name: str) -> ItemStatus:
    return ItemStatus(path=name, name=name, state="skipped", detail="x")


def test_all_ok_returns_zero() -> None:
    items = [_ok(f"item_{i}") for i in range(16)]
    assert compute_exit_code(items, force=False, pre_condition_code=0, sqlite_setup_failed=False) == 0


def test_warning_alone_returns_zero() -> None:
    """FR-007: warning is SOFT — must not contribute to non-zero exit."""
    items = [_ok(f"item_{i}") for i in range(15)] + [_warning("provider.toml")]
    assert compute_exit_code(items, force=False) == 0


def test_warning_plus_ok_mix_returns_zero() -> None:
    items = [_warning("provider.toml")] + [_ok(f"item_{i}") for i in range(15)]
    assert compute_exit_code(items, force=False) == 0


def test_error_without_force_returns_six() -> None:
    items = [_ok(f"item_{i}") for i in range(15)] + [_error("provider.toml")]
    assert compute_exit_code(items, force=False) == 6


def test_error_with_force_returns_seven() -> None:
    items = [_ok(f"item_{i}") for i in range(15)] + [_error("provider.toml")]
    assert compute_exit_code(items, force=True) == 7


def test_pre_condition_two_wins_over_everything() -> None:
    """Clarification Q5: pre-condition 2 takes precedence."""
    items = [_ok(f"item_{i}") for i in range(16)]
    assert compute_exit_code(items, force=False, pre_condition_code=2) == 2
    # Even with errors + force, pre-condition wins
    items = [_error(f"item_{i}") for i in range(16)]
    assert compute_exit_code(items, force=True, pre_condition_code=2) == 2


def test_pre_condition_five_wins_over_everything() -> None:
    items = [_error(f"item_{i}") for i in range(16)]
    assert compute_exit_code(items, force=False, pre_condition_code=5) == 5


def test_skipped_alone_returns_zero() -> None:
    items = [_skipped("memory/store.sqlite3")]
    assert compute_exit_code(items, force=False) == 0


def test_sqlite_setup_failed_returns_four() -> None:
    """T012c: SqliteSaver.setup() OSError -> 4 (FR-007 + spec L154).

    Code 4 wins regardless of any other item state.
    """
    items = [_ok(f"item_{i}") for i in range(15)] + [_error("memory/checkpoint.sqlite3")]
    assert compute_exit_code(items, force=False, sqlite_setup_failed=True) == 4


def test_sqlite_setup_failed_wins_over_force_seven() -> None:
    items = [_ok(f"item_{i}") for i in range(14)] + [
        _error("memory/checkpoint.sqlite3"),
        _error("provider.toml"),
    ]
    # sqlite_setup_failed=True -> 4 (not 7)
    assert compute_exit_code(items, force=True, sqlite_setup_failed=True) == 4


def test_created_and_ok_mix_returns_zero() -> None:
    items = [_created(f"item_{i}") for i in range(15)] + [_skipped("memory/store.sqlite3")]
    assert compute_exit_code(items, force=False) == 0