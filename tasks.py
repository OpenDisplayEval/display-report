"""OLE-Toolset development tasks powered by Invoke."""

from __future__ import annotations

import shutil
from pathlib import Path

from invoke import Context, task

ROOT = Path(__file__).resolve().parent


@task
def lint(ctx: Context, fix: bool = False) -> None:
    """Run ruff linter."""
    cmd = "ruff check ."
    if fix:
        cmd += " --fix"
    ctx.run(cmd, pty=True)


@task
def format(ctx: Context, check: bool = False) -> None:
    """Run ruff formatter."""
    cmd = "ruff format ."
    if check:
        cmd += " --check"
    ctx.run(cmd, pty=True)


@task
def typecheck(ctx: Context) -> None:
    """Run pyright type checker."""
    ctx.run("pyright", pty=True)


@task
def spellcheck(ctx: Context) -> None:
    """Run cspell spell checker."""
    ctx.run('npx cspell "ole/**/*" "tests/**/*" "*.md"', pty=True)


@task
def check(ctx: Context) -> None:
    """Run all quality checks (lint, format --check, typecheck, spellcheck)."""
    lint(ctx)
    format(ctx, check=True)
    typecheck(ctx)
    spellcheck(ctx)


@task(name="check-fix")
def check_fix(ctx: Context) -> None:
    """Run lint --fix and format."""
    lint(ctx, fix=True)
    format(ctx)


@task
def test(ctx: Context) -> None:
    """Run pytest test suite."""
    ctx.run("python -m pytest", pty=True)


@task
def clean(ctx: Context) -> None:  # noqa: ARG001
    """Remove build artifacts and caches."""
    patterns = ["__pycache__", ".pytest_cache", ".ruff_cache"]
    for pattern in patterns:
        for path in ROOT.rglob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"Removed {path}")


@task(name="ai-developer-quality")
def ai_developer_quality(ctx: Context) -> None:
    """Run quality checks suitable for AI-assisted development."""
    format(ctx)
    lint(ctx, fix=True)
    typecheck(ctx)
    spellcheck(ctx)


@task
def dev(ctx: Context) -> None:
    """Run full development workflow (check-fix, typecheck, spellcheck, test)."""
    check_fix(ctx)
    typecheck(ctx)
    spellcheck(ctx)
    test(ctx)
