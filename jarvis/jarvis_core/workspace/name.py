"""--name validation and default-name derivation (T004).

Per spec FR-002 and clarification Q1:
- validate_name(name): regex ^[A-Za-z0-9_\u4e00-\u9fff+-]+$; empty rejected.
- derive_default_name(path): last path segment with final dot-prefixed
  extension stripped; e.g., agent.git -> agent; report.md -> report;
  a/b/c -> c; .gitignore -> ''; '.' -> ''; '/' -> ''.
"""

from __future__ import annotations

import re
from pathlib import Path


NAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff+-]+$")


def validate_name(name: str) -> bool:
    """True iff name matches the spec FR-002 regex (non-empty)."""
    if not isinstance(name, str) or not name:
        return False
    return NAME_PATTERN.fullmatch(name) is not None


def derive_default_name(path: Path) -> str:
    """Last path segment with final dot-prefixed extension stripped (Q1).

    Edge cases (Q1, all return ''):
    - pure hidden filename ('.gitignore' -> '')
    - single-char path ('.' -> '')
    - root ('/' -> '')
    """
    name = path.name
    if not name:
        return ""
    if name.startswith("."):
        return ""
    # Strip final dot-prefixed extension (e.g., "agent.git" -> "agent",
    # "report.md" -> "report"); keep "my.agent" -> "my" (only last dot stripped).
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name