"""16-item registry with create/check functions (T006, T016-T024, T034).

The 16 items are in the order specified by spec FR-001. Each item has:
- relpath: relative path under the workspace root
- kind: 'FILE' or 'DIRECTORY'
- is_user_data: True for items whose content belongs to the user
- create_fn: writes the default content; takes (path, ...) with item-specific
  kwargs pre-bound via partial in the registry (per T006 scheduling contract).
- check_fn: returns ItemStatus(state, detail); NEVER modifies the file.

The `memory/store.sqlite3` item has no create_fn (always skipped, per FR-004).
The `memory/checkpoint.sqlite3` check uses byte-level header only (NFR-001a).

The --force overwrite path (US3 / T034 / T035) calls create_fn again only for
items where (a) check returned 'error' AND (b) is_user_data is False.
"""

from __future__ import annotations

import functools
import json
import os
import sqlite3
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from . import templates
from .status import ItemStatus


SQLITE_HEADER = b"SQLite format 3\x00"


CheckResult = Literal["ok", "warning", "error", "skipped"]


# ---------------------------------------------------------------------------
# ItemSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemSpec:
    """One entry in the 16-item registry (T006)."""

    relpath: str
    kind: Literal["FILE", "DIRECTORY"]
    is_user_data: bool
    create_fn: Callable[..., None] | None
    check_fn: Callable[..., ItemStatus]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def check_checkpoint_sqlite_header(path: Path) -> CheckResult:
    """NFR-001a byte-level header check (T023a). Reads first 16 bytes only.

    Returns 'ok' iff bytes == b"SQLite format 3\\x00", else 'error'.
    NEVER calls sqlite3.connect() (NFR-001a). NEVER touches the file beyond
    reading the header.
    """
    if not path.exists():
        return "error"
    try:
        with open(path, "rb") as f:
            header = f.read(16)
    except OSError:
        return "error"
    if len(header) < 16:
        return "error"
    if header != SQLITE_HEADER:
        return "error"
    return "ok"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _format_bytes(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# instruction.md  (FR-008, T016)
# ---------------------------------------------------------------------------


def _instruction_md_create(path: Path, *, name: str, timestamp: str, abs_path: str) -> None:
    _ensure_parent(path)
    body = templates.INSTRUCTION_MD_TEMPLATE.format(
        NAME=name,
        TIMESTAMP=timestamp,
        PATH=abs_path,
    )
    path.write_text(body, encoding="utf-8")


def _instruction_md_check(path: Path, *, name: str) -> ItemStatus:
    if not path.exists():
        return ItemStatus(path=str(path), name=path.name, state="error", detail="file missing")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ItemStatus(path=str(path), name=path.name, state="error", detail=str(exc))
    if not text.strip():
        return ItemStatus(path=str(path), name=path.name, state="warning", detail="empty file")
    first_line = text.splitlines()[0] if text else ""
    expected = f"# {name}"
    if first_line.strip() != expected:
        return ItemStatus(
            path=str(path),
            name=path.name,
            state="warning",
            detail=f"first line not '{expected}'",
        )
    return ItemStatus(path=str(path), name=path.name, state="ok")


# ---------------------------------------------------------------------------
# provider.toml  (FR-009, T017)
# ---------------------------------------------------------------------------


def _provider_toml_create(path: Path) -> None:
    _ensure_parent(path)
    path.write_text(templates.PROVIDER_TOML_TEMPLATE, encoding="utf-8")


def _provider_toml_check(path: Path) -> ItemStatus:
    name = path.name
    if not path.exists():
        return ItemStatus(path=str(path), name=name, state="error", detail="file missing")
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        return ItemStatus(
            path=str(path),
            name=name,
            state="error",
            detail=f"TOML parse error: {exc!s}",
        )
    if "provider" not in data:
        return ItemStatus(
            path=str(path),
            name=name,
            state="warning",
            detail="missing [provider] section",
        )
    if "extra" not in data["provider"]:
        return ItemStatus(
            path=str(path),
            name=name,
            state="error",
            detail="missing [provider.extra] section",
        )
    return ItemStatus(path=str(path), name=name, state="ok")


# ---------------------------------------------------------------------------
# Directory items  (T022)
# ---------------------------------------------------------------------------


def _dir_create(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def _dir_check(path: Path) -> ItemStatus:
    name = path.name
    if not path.exists():
        return ItemStatus(path=str(path), name=name, state="error", detail="missing")
    if not path.is_dir():
        return ItemStatus(
            path=str(path),
            name=name,
            state="error",
            detail="path exists but is a regular file",
        )
    return ItemStatus(path=str(path), name=name, state="ok")


def _memory_dir_create(path: Path, *, force: bool = False) -> None:
    """memory/ special handling per clarification Q3.

    Without --force: regular file in the way -> caller already raised 'error'.
    With --force: remove the conflicting file then mkdir.
    """
    if path.exists() and not path.is_dir():
        if not force:
            # Should not be reached — check() returned 'error' before this point
            # and orchestrator should not have called create_fn in that case.
            raise FileExistsError(f"{path} exists but is a regular file")
        os.remove(path)
    path.mkdir(parents=True, exist_ok=False)


# ---------------------------------------------------------------------------
# Empty file items
# ---------------------------------------------------------------------------


def _empty_file_create(path: Path) -> None:
    _ensure_parent(path)
    path.write_text("", encoding="utf-8")


def _file_exists_check(path: Path) -> ItemStatus:
    name = path.name
    if not path.exists():
        return ItemStatus(path=str(path), name=name, state="error", detail="file missing")
    return ItemStatus(path=str(path), name=name, state="ok")


def _nonempty_file_check(path: Path) -> ItemStatus:
    name = path.name
    if not path.exists():
        return ItemStatus(path=str(path), name=name, state="error", detail="file missing")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ItemStatus(path=str(path), name=name, state="error", detail=str(exc))
    if not text.strip():
        return ItemStatus(path=str(path), name=name, state="warning", detail="empty file")
    return ItemStatus(path=str(path), name=name, state="ok")


# ---------------------------------------------------------------------------
# README / template files  (T019, T021)
# ---------------------------------------------------------------------------


def _readme_create(path: Path, template: str) -> None:
    _ensure_parent(path)
    path.write_text(template, encoding="utf-8")


def _mcp_json_create(path: Path) -> None:
    _ensure_parent(path)
    path.write_text(templates.MCP_JSON_EMPTY, encoding="utf-8")


def _mcp_json_check(path: Path) -> ItemStatus:
    name = path.name
    if not path.exists():
        return ItemStatus(path=str(path), name=name, state="error", detail="file missing")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return ItemStatus(
            path=str(path),
            name=name,
            state="error",
            detail=f"JSON parse error: {exc!s}",
        )
    if not isinstance(data, dict) or "mcpServers" not in data:
        return ItemStatus(
            path=str(path),
            name=name,
            state="error",
            detail="missing top-level 'mcpServers' key",
        )
    return ItemStatus(path=str(path), name=name, state="ok")


def _skills_example_md_create(path: Path) -> None:
    _ensure_parent(path)
    path.write_text(templates.SKILLS_EXAMPLE_MD, encoding="utf-8")


def _skills_example_md_check(path: Path) -> ItemStatus:
    name = path.name
    if not path.exists():
        return ItemStatus(path=str(path), name=name, state="error", detail="file missing")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ItemStatus(path=str(path), name=name, state="error", detail=str(exc))
    if not text.strip():
        return ItemStatus(path=str(path), name=name, state="warning", detail="empty file")
    if not text.startswith("---"):
        return ItemStatus(
            path=str(path),
            name=name,
            state="warning",
            detail="missing YAML frontmatter",
        )
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ItemStatus(
            path=str(path),
            name=name,
            state="warning",
            detail="unterminated YAML frontmatter",
        )
    import yaml
    try:
        yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        return ItemStatus(
            path=str(path),
            name=name,
            state="error",
            detail=f"YAML frontmatter parse error: {exc!s}",
        )
    return ItemStatus(path=str(path), name=name, state="ok")


# ---------------------------------------------------------------------------
# checkpoint.sqlite3  (T023, NFR-001a)
# ---------------------------------------------------------------------------


def _checkpoint_sqlite_create(path: Path) -> None:
    """First-time init only (T023). Opens sqlite, runs SqliteSaver.setup, closes.

    If SqliteSaver.setup() raises (e.g., OSError), the orchestrator must
    catch it and set sqlite_setup_failed=True) -> exit code 4.
    """
    _ensure_parent(path)
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(path))
    try:
        saver = SqliteSaver(conn)
        saver.setup()
    finally:
        conn.close()


def _checkpoint_sqlite_check(path: Path) -> ItemStatus:
    """Byte-level header check only (NFR-001a).

    Forbidden: sqlite3.connect(), schema validation, WAL recovery.
    """
    name = path.name
    if not path.exists():
        return ItemStatus(path=str(path), name=name, state="error", detail="file missing")
    result = check_checkpoint_sqlite_header(path)
    if result == "ok":
        size_mb = path.stat().st_size / (1024 * 1024)
        return ItemStatus(
            path=str(path),
            name=name,
            state="ok",
            detail=f"保留 {_format_bytes(path.stat().st_size)} 用户数据",
        )
    return ItemStatus(
        path=str(path),
        name=name,
        state="error",
        detail="not a valid SQLite file (header magic mismatch)",
    )


# ---------------------------------------------------------------------------
# store.sqlite3  (T024, FR-004)
# ---------------------------------------------------------------------------


def _store_sqlite_check(path: Path) -> ItemStatus:
    """Always skipped, stat-only per FR-004 + clarification Q2."""
    name = path.name
    if path.exists():
        detail = "已存在，未校验"
    else:
        detail = "Scheduler 阶段创建"
    return ItemStatus(path=str(path), name=name, state="skipped", detail=detail)


# ---------------------------------------------------------------------------
# Helpers used by init_workspace (T007a)
# ---------------------------------------------------------------------------


def check_no_python_entries(path: Path) -> None:
    """Raise ValueError if any FR-015 forbidden entry exists under path.

    Used by tests; jarvis_core/init.py does NOT call this.
    """
    forbidden = [
        "agent.py",
        "main.py",
        "subagent",
        "subagent.py",
        "middleware",
        "connectors",
        "channels",
        "schedules",
        "evals",
        "identity",
        "memory.py",
        "sandbox",
    ]
    bad: list[str] = []
    for entry in forbidden:
        candidate = path / entry
        if candidate.exists():
            bad.append(entry)
    # mcp/*.py
    mcp_dir = path / "mcp"
    if mcp_dir.is_dir():
        for p in mcp_dir.glob("*.py"):
            bad.append(str(p.relative_to(path)))
    if bad:
        raise ValueError(f"forbidden workspace entries present: {bad}")


REQUIRED_ITEMS: tuple[str, ...] = (
    "instruction.md",
    "provider.toml",
    "tools",
    "tools/__init__.py",
    "tools/README.md",
    "mcp",
    "mcp/mcp.json",
    "mcp/README.md",
    "skills",
    "skills/README.md",
    "skills/example/SKILL.md",
    "memory",
    "memory/checkpoint.sqlite3",
    "memory/store.sqlite3",
    "memory/README.md",
    "README.md",
)


def check_required_items(path: Path) -> bool:
    """Return True iff all 16 items per spec FR-001 exist."""
    for relpath in REQUIRED_ITEMS:
        if not (path / relpath).exists():
            return False
    return True


# ---------------------------------------------------------------------------
# Registry  (T006 + T016-T024)
# ---------------------------------------------------------------------------


def register_all_items(
    *,
    name: str,
    timestamp: str,
    abs_path: str,
) -> list[ItemSpec]:
    """Return the 16-item registry in spec FR-001 order.

    Each create_fn is wrapped in functools.partial with item kwargs pre-supplied;
    init_workspace uniformly calls bound_fn(path) (or bound_fn(path, force=True)
    for --force overwrite of error items).

    For store.sqlite3, create_fn is None (never created, per FR-004).
    """

    def bind(fn: Callable[..., None], **kwargs: object) -> Callable[..., None]:
        return functools.partial(fn, **kwargs)

    return [
        ItemSpec(
            relpath="instruction.md",
            kind="FILE",
            is_user_data=False,
            create_fn=bind(
                _instruction_md_create,
                name=name,
                timestamp=timestamp,
                abs_path=abs_path,
            ),
            check_fn=functools.partial(_instruction_md_check, name=name),
        ),
        ItemSpec(
            relpath="provider.toml",
            kind="FILE",
            is_user_data=False,
            create_fn=_provider_toml_create,
            check_fn=_provider_toml_check,
        ),
        ItemSpec(
            relpath="tools",
            kind="DIRECTORY",
            is_user_data=False,
            create_fn=_dir_create,
            check_fn=_dir_check,
        ),
        ItemSpec(
            relpath="tools/__init__.py",
            kind="FILE",
            is_user_data=False,
            create_fn=_empty_file_create,
            check_fn=_file_exists_check,
        ),
        ItemSpec(
            relpath="tools/README.md",
            kind="FILE",
            is_user_data=False,
            create_fn=functools.partial(_readme_create, template=templates.TOOLS_README),
            check_fn=_nonempty_file_check,
        ),
        ItemSpec(
            relpath="mcp",
            kind="DIRECTORY",
            is_user_data=False,
            create_fn=_dir_create,
            check_fn=_dir_check,
        ),
        ItemSpec(
            relpath="mcp/mcp.json",
            kind="FILE",
            is_user_data=False,
            create_fn=_mcp_json_create,
            check_fn=_mcp_json_check,
        ),
        ItemSpec(
            relpath="mcp/README.md",
            kind="FILE",
            is_user_data=False,
            create_fn=functools.partial(_readme_create, template=templates.MCP_README),
            check_fn=_nonempty_file_check,
        ),
        ItemSpec(
            relpath="skills",
            kind="DIRECTORY",
            is_user_data=False,
            create_fn=_dir_create,
            check_fn=_dir_check,
        ),
        ItemSpec(
            relpath="skills/README.md",
            kind="FILE",
            is_user_data=False,
            create_fn=functools.partial(_readme_create, template=templates.SKILLS_README),
            check_fn=_nonempty_file_check,
        ),
        ItemSpec(
            relpath="skills/example/SKILL.md",
            kind="FILE",
            is_user_data=False,
            create_fn=_skills_example_md_create,
            check_fn=_skills_example_md_check,
        ),
        ItemSpec(
            relpath="memory",
            kind="DIRECTORY",
            is_user_data=False,
            create_fn=functools.partial(_memory_dir_create),
            check_fn=_dir_check,
        ),
        ItemSpec(
            relpath="memory/checkpoint.sqlite3",
            kind="FILE",
            is_user_data=True,
            create_fn=_checkpoint_sqlite_create,
            check_fn=_checkpoint_sqlite_check,
        ),
        ItemSpec(
            relpath="memory/store.sqlite3",
            kind="FILE",
            is_user_data=False,
            create_fn=None,
            check_fn=_store_sqlite_check,
        ),
        ItemSpec(
            relpath="memory/README.md",
            kind="FILE",
            is_user_data=False,
            create_fn=functools.partial(_readme_create, template=templates.MEMORY_README),
            check_fn=_nonempty_file_check,
        ),
        ItemSpec(
            relpath="README.md",
            kind="FILE",
            is_user_data=False,
            create_fn=functools.partial(_readme_create, template=templates.TOP_LEVEL_README),
            check_fn=_nonempty_file_check,
        ),
    ]


__all__ = [
    "ItemSpec",
    "REQUIRED_ITEMS",
    "check_checkpoint_sqlite_header",
    "check_no_python_entries",
    "check_required_items",
    "register_all_items",
]