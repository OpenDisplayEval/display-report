"""Command-line entry point.

Dispatches ``display-report <command>`` to the matching script module. Each
command owns its own argument parser, so ``display-report analyze --help``
shows that command's options.
"""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

COMMANDS: dict[str, tuple[str, str]] = {
    "analyze": (
        "display_report.scripts.analyze_display_measurements",
        "Analyze a .csmf measurement file and write a PDF fidelity report",
    ),
    "anonymize": (
        "display_report.scripts.strip_metadata",
        "Strip identifying metadata from a measurement file",
    ),
}


def usage() -> str:
    """Render the top-level help text."""
    width = max(len(name) for name in COMMANDS)
    lines = ["usage: display-report <command> [options]", "", "commands:"]
    lines += [
        f"  {name:<{width}}  {description}"
        for name, (_, description) in COMMANDS.items()
    ]
    lines += ["", "Run 'display-report <command> --help' for a command's options."]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to a subcommand. Returns the process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)

    if not args:
        print(usage(), file=sys.stderr)
        return 2

    command, *rest = args

    if command in {"-h", "--help"}:
        print(usage())
        return 0

    if command not in COMMANDS:
        print(f"display-report: unknown command {command!r}\n", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2

    module_name, _ = COMMANDS[command]
    handler = importlib.import_module(module_name).main

    saved_argv = sys.argv
    sys.argv = [f"display-report {command}", *rest]
    try:
        handler()
    finally:
        sys.argv = saved_argv
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
