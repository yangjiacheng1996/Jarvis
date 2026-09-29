"""CLI entry point: jarvis cli_client.jarvis_cli:cli_main.

Per spec FR-017 + constitution §3 / §8 + contracts/cli.md Layer Boundary:
- Imports only argparse / sys / pathlib / jarvis_core.
- cli_main() is the entry point for both python -m jarvis and the
  `jarvis` console script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jarvis import jarvis_core as jarvis_core_pkg


def run_init(args: argparse.Namespace) -> int:
    """Handle the `init` subcommand (T027 + T037 + T040).

    Flow:
        1. Validate args.name (if given); on failure -> exit 5.
        2. Derive default name from path when args.name is None.
        3. Call jarvis_core.init_workspace(...).
        4. Print render_summary(result).
        5. On exit_code == 0, append follow-up line and return 0.
    """

    name = args.name
    path = Path(args.path)
    force = bool(args.force)

    if name is not None and not jarvis_core_pkg.validate_name(name):
        # FR-002: print clear stderr message identifying offending chars.
        invalid_chars = sorted(
            {c for c in name if not _is_allowed_char(c)},
            key=lambda c: ord(c),
        )
        sys.stderr.write(
            "错误：--name 只能包含 ASCII 字母、数字、下划线、中文、加号、减号；"
            f"非法字符: {', '.join(repr(c) for c in invalid_chars)}\n"
        )
        return 5

    # Derive default name when --name is not provided.
    if name is None:
        name = jarvis_core_pkg.derive_default_name(path)

    result = jarvis_core_pkg.init_workspace(path=path, name=name, force=force)

    output = jarvis_core_pkg.render_summary(result)

    if result.exit_code == 0:
        output += (
            "\n"
            f"Workspace '{result.name}' 已生成，请编辑 instruction.md / provider.toml 后运行 "
            f"`jarvis run`。"
        )
    else:
        # Surface a per-item error message to stderr for non-zero exits that
        # left some file untouched.
        for it in result.items:
            if it.state == "error" and it.detail:
                sys.stderr.write(f"{it.name}: {it.detail}\n")

    sys.stdout.write(output + "\n")
    return result.exit_code


def _is_allowed_char(c: str) -> bool:
    """True iff c is allowed in --name per spec FR-002 regex."""
    if not c:
        return False
    if "A" <= c <= "Z" or "a" <= c <= "z" or "0" <= c <= "9":
        return True
    if c in "_+-":
        return True
    cp = ord(c)
    return 0x4E00 <= cp <= 0x9FFF


def cli_main() -> int:
    """Console-script entry point (T010 + T027).

    Builds the top-level argparse parser with `init` subcommand.
    Wraps everything in a top-level try/except that returns 1 (per spec FR-007).
    """
    try:
        parser = argparse.ArgumentParser(prog="jarvis", description="Jarvis Core CLI")
        subparsers = parser.add_subparsers(dest="command", required=True)

        init_p = subparsers.add_parser("init", help="Initialize a workspace")
        init_p.add_argument(
            "path",
            nargs="?",
            default=".",
            help="Target workspace directory (default: current directory)",
        )
        init_p.add_argument(
            "--name",
            default=None,
            help="Agent identity injected into instruction.md",
        )
        init_p.add_argument(
            "--force",
            action="store_true",
            help="Overwrite items whose check returned 'error' (excludes user data)",
        )

        args = parser.parse_args()
        if args.command == "init":
            return run_init(args)
        parser.print_help()
        return 1
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"错误：{exc!r}\n")
        return 1


__all__ = ["cli_main", "run_init"]