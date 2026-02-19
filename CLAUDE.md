# CLAUDE.md — OLE-Toolset

## Project overview

OLE-Toolset (OpenLEDEval Toolset) is a display measurement and analysis toolkit for
LED/OLED display evaluation. It provides command-line tools for driving test pattern
generators, capturing spectroradiometer measurements, and analyzing the resulting data
to produce reports.

## Common commands

All commands must be run through `uv run` to use the project's virtual environment:

```bash
uv run invoke check          # Run all quality checks (lint, format --check, typecheck, spellcheck)
uv run invoke check-fix      # Auto-fix lint and format issues
uv run invoke test            # Run pytest suite
uv run invoke typecheck       # Run pyright
uv run invoke spellcheck      # Run cspell
uv run invoke ai-developer-quality  # Format + lint fix + typecheck + spellcheck
uv run invoke dev             # Full dev workflow: check-fix + typecheck + spellcheck + test
uv run invoke clean           # Remove __pycache__, .pytest_cache, .ruff_cache
```

## Development guidelines

- **DRY**: Do not repeat yourself. Reuse existing utilities from `ole.utilities`.
- **Docstrings**: Use NumPy-style docstrings for all public functions and classes.
- **Type hints**: All function signatures must have type annotations.
- **Always use `uv run`**: Never invoke tools directly; always prefix with `uv run`.
- **Formatting**: ruff handles both linting and formatting (line length 88).
- **Imports**: ruff handles import sorting; `ole` is a known first-party package.

## Entry points

| Command | Module | Description |
|---------|--------|-------------|
| `ole_measure` | `ole.scripts.measure_display:main` | Drive TPG + spectroradiometer for measurements |
| `ole_analyze` | `ole.scripts.analyze_display_measurements:main` | Analyze measurement data and generate reports |
| `ole_anonymize` | `ole.scripts.strip_metadata:main` | Strip identifying metadata from measurement files |

## Package structure

- `ole/` — Main package
  - `scripts/` — CLI entry points
  - `ETC/` — Analysis and PDF report generation
  - `utilities.py` — Shared helper functions
  - `measurement_controllers.py` — Spectroradiometer control
  - `tpg_controller.py` — Test pattern generator control
  - `test_colors.py` — Test colour definitions

## Error handling

- Use specific exception types; avoid bare `except`.
- Let unexpected errors propagate — do not silently swallow exceptions.
- For user-facing CLI errors, print a clear message and `sys.exit(1)`.

## Claude Code agent workflow

After making changes:

1. Run `uv run invoke ai-developer-quality` to format, lint-fix, typecheck, and spellcheck.
2. Re-read any files you modified (they may have been auto-formatted).
3. Run `uv run invoke test` to verify nothing is broken.
