"""init_workspace orchestrator (T007, T025, T025a, T030, T035).

Public surface:
    init_workspace(path, name=None, force=False) -> InitResult

Per contracts/library-api.md and contracts/item-status.md.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .items import ItemSpec, register_all_items
from .name import derive_default_name, validate_name
from .status import InitResult, ItemStatus, compute_exit_code, count_items
from . import templates


log = logging.getLogger(__name__)


class SqliteSetupError(RuntimeError):
    """Raised internally when checkpoint sqlite setup fails (FR-007 exit 4)."""


def init_workspace(
    path: Path,
    name: str | None = None,
    force: bool = False,
) -> InitResult:
    """Idempotently create / verify a workspace.

    See spec.md and contracts/cli.md for full behavior.
    """

    abs_path = Path(path).resolve()

    # ---- Pre-condition 1: PATH validation (clarification Q5) ----
    if abs_path.exists() and not abs_path.is_dir():
        return InitResult(path=abs_path, name=name or "", exit_code=2)
    if not abs_path.parent.exists():
        return InitResult(path=abs_path, name=name or "", exit_code=2)

    # ---- Pre-condition 2: name validation (FR-002) ----
    if name is None:
        name = derive_default_name(abs_path)
    if not validate_name(name):
        return InitResult(path=abs_path, name=name, exit_code=5)

    # Make sure the workspace root exists (single-layer mkdir only)
    abs_path.mkdir(parents=False, exist_ok=True)

    # ---- Per-item registry ----
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry = register_all_items(name=name, timestamp=timestamp, abs_path=str(abs_path))

    items, sqlite_setup_failed = _process_registry(registry, abs_path, force=force)

    counts = count_items(items)
    exit_code = compute_exit_code(
        items,
        force=force,
        pre_condition_code=0,
        sqlite_setup_failed=sqlite_setup_failed,
    )

    # ---- Side-effect: write .gitignore (FR-013, NOT in items) ----
    _write_gitignore(abs_path)

    return InitResult(
        path=abs_path,
        name=name,
        items=items,
        counts=counts,
        exit_code=exit_code,
    )


def _process_registry(
    registry: Iterable[ItemSpec],
    abs_path: Path,
    *,
    force: bool,
) -> tuple[list[ItemStatus], bool]:
    """Walk the 16-item registry and produce ItemStatus + sqlite_setup_failed flag."""

    items: list[ItemStatus] = []
    sqlite_setup_failed = False

    for item in registry:
        target = abs_path / item.relpath
        if not target.exists():
            # CREATE path
            status = _create_item(item, target, force=force)
            items.append(status)
            if status.state == "error" and "SqliteSetupError" in (status.detail or ""):
                sqlite_setup_failed = True
        else:
            # CHECK path (read-only by contract)
            try:
                status = item.check_fn(target)
                # Force the relpath on ItemStatus so the renderer shows full path.
                status = ItemStatus(
                    path=str(target),
                    name=item.relpath,
                    state=status.state,
                    detail=status.detail,
                )
            except Exception as exc:  # pragma: no cover - defensive
                status = ItemStatus(
                    path=str(target),
                    name=item.relpath,
                    state="error",
                    detail=f"check raised: {exc!r}",
                )
            items.append(status)
            # US3 / T035: --force may overwrite error items that are NOT user data.
            if (
                force
                and status.state == "error"
                and not item.is_user_data
                and item.create_fn is not None
            ):
                try:
                    _create_item(item, target, force=True)
                    items[-1] = ItemStatus(
                        path=str(target),
                        name=item.relpath,
                        state="overwritten",
                    )
                except Exception as exc:
                    items[-1] = ItemStatus(
                        path=str(target),
                        name=item.relpath,
                        state="error",
                        detail=f"create failed: {exc!r}",
                    )

    return items, sqlite_setup_failed


def _create_item(item: ItemSpec, target: Path, *, force: bool) -> ItemStatus:
    """Invoke create_fn with proper kwargs; handle SqliteSetupError (T025a).

    Returns ItemStatus with state='created' on success, 'skipped' for items
    with no create_fn, or 'error' on failure. SqliteSetupError is captured
    into detail so the orchestrator can mark sqlite_setup_failed=True.

    Revised 2026-09-30: no item currently uses the create_fn-None branch
    (memory/store.sqlite3 now has a create_fn per FR-019). The branch is
    retained as a safety net for future items that opt to skip creation.
    """
    if item.create_fn is None:
        # Safety net — no current item has create_fn=None post-amendment.
        # Retained for forward compatibility (e.g., a future "opt-out" item).
        return ItemStatus(
            path=str(target),
            name=item.relpath,
            state="skipped",
            detail="no create_fn registered",
        )

    # Determine which kwargs create_fn accepts
    try:
        if force and _accepts_force(item.create_fn):
            item.create_fn(target, force=True)
        else:
            item.create_fn(target)
    except Exception as exc:
        # SqliteSetupError is reserved for SqliteSaver.setup() failures on
        # the checkpoint item. Other items (or non-setup OSError failures on
        # e.g. parent dir creation) are reported as generic create failures.
        is_sqlite_setup_failure = (
            item.relpath == "memory/checkpoint.sqlite3"
            and _is_sqlite_setup_failure(exc)
        )
        detail = (
            f"SqliteSetupError: {exc!r}"
            if is_sqlite_setup_failure
            else f"create failed: {exc!r}"
        )
        return ItemStatus(
            path=str(target),
            name=item.relpath,
            state="error",
            detail=detail,
        )

    return ItemStatus(
        path=str(target),
        name=item.relpath,
        state="created",
    )


def _accepts_force(fn) -> bool:
    """True if the partial-wrapped callable accepts a 'force' kwarg."""
    inner = getattr(fn, "func", fn)
    try:
        import inspect

        sig = inspect.signature(inner)
    except (TypeError, ValueError):
        return False
    return "force" in sig.parameters


def _is_sqlite_setup_failure(exc: BaseException) -> bool:
    """True iff exc looks like a SqliteSaver.setup() failure.

    Per spec FR-007: SqliteSaver.setup() may raise OSError (e.g., disk full,
    permission denied) or sqlite3.OperationalError. We classify those as
    SqliteSetupError; FileExistsError is excluded — that's a generic fs error
    not specific to sqlite setup.
    """
    if isinstance(exc, sqlite3.OperationalError):
        return True
    if isinstance(exc, OSError) and not isinstance(exc, FileExistsError):
        return True
    return False


def _write_gitignore(abs_path: Path) -> None:
    """Side-effect write of .gitignore (FR-013). Not part of 16-item registry."""
    gitignore = abs_path / ".gitignore"
    gitignore.write_text(templates.GITIGNORE, encoding="utf-8")


__all__ = ["init_workspace", "SqliteSetupError"]