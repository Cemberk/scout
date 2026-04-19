"""CLI entry point: python -m evals

Subcommands:
    python -m evals                      # run every static eval category
    python -m evals --category routing   # single static category
    python -m evals smoke                # run in-process smoke tier
    python -m evals improve              # autonomous improvement loop
"""

from __future__ import annotations

import argparse
import sys

from evals import CATEGORIES
from evals.run import run_evals


def _dispatch_smoke(argv: list[str]) -> int:
    from evals.smoke import _cli_exit_code, run_smoke_tests

    p = argparse.ArgumentParser(prog="python -m evals smoke", description="Scout smoke tests (in-process)")
    p.add_argument("--group", type=str, help="Filter to one group (warmup|routing|governance|wiki|knowledge|gating)")
    p.add_argument("--case", dest="case_id", type=str, help="Run a single case by id")
    p.add_argument("--verbose", action="store_true", help="Show response + tool previews")
    a = p.parse_args(argv)
    results = run_smoke_tests(group=a.group, case_id=a.case_id, verbose=a.verbose)
    return _cli_exit_code(results)


def _dispatch_improve(argv: list[str]) -> int:
    from evals.improve import run_improvement_loop

    p = argparse.ArgumentParser(prog="python -m evals improve", description="Scout autonomous improve loop")
    p.add_argument("--rounds", type=int, default=3, help="Max improvement rounds (default: 3)")
    p.add_argument(
        "--tier",
        choices=["smoke", "live", "static", "all"],
        default="smoke",
        help="Which eval tier to drive the loop from (default: smoke)",
    )
    p.add_argument("--dry-run", action="store_true", help="Analyze + print diff, don't edit or commit")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--no-commit", action="store_true", help="Run the loop but don't git-commit successful rounds")
    a = p.parse_args(argv)
    ok = run_improvement_loop(
        rounds=a.rounds,
        tier=a.tier,
        dry_run=a.dry_run,
        verbose=a.verbose,
        commit=not a.no_commit,
    )
    return 0 if ok else 1


def _dispatch_default(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m evals", description="Run Scout static evals")
    p.add_argument("--category", type=str, choices=list(CATEGORIES.keys()), help="Run a single category")
    p.add_argument("--verbose", action="store_true", help="Show response previews and failure reasons")
    a = p.parse_args(argv)
    run_evals(category=a.category, verbose=a.verbose)
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "smoke":
        return _dispatch_smoke(argv[1:])
    if argv and argv[0] == "improve":
        return _dispatch_improve(argv[1:])
    return _dispatch_default(argv)


if __name__ == "__main__":
    sys.exit(main())
