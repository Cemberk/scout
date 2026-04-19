"""Scout evals CLI.

    python -m evals                        # behavioral, in-process, all cases
    python -m evals --case <id>            # single case
    python -m evals --live                 # same cases via Docker SSE
    python -m evals --verbose              # show responses + tool previews

    python -m evals wiring                 # code-level invariants (no LLM)
    python -m evals judges                 # LLM-scored quality tier
    python -m evals judges --case <id>

Exit code: 0 if all PASS or SKIP, 1 if any FAIL or ERROR.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evals.cases import CASES, REPO_ROOT, get
from evals.runner import CaseResult, run_case, write_diagnostic

_COLORS = {"PASS": "\033[32m", "FAIL": "\033[31m", "ERROR": "\033[31m", "SKIPPED": "\033[33m"}
_RESET = "\033[0m"


def _tag(status: str) -> str:
    if sys.stdout.isatty():
        return f"{_COLORS.get(status, '')}{status:<7}{_RESET}"
    return f"{status:<7}"


# ---------------------------------------------------------------------------
# Behavioral dispatch (default)
# ---------------------------------------------------------------------------


def _print_case(r: CaseResult, diagnostic: Path | None, verbose: bool) -> None:
    print(f"[{_tag(r.status)}] {r.case_id:<40} ({r.duration_s:.1f}s) [{r.transport}]")
    if r.skipped_reason:
        print(f"            {r.skipped_reason}")
    for f in r.failures:
        print(f"            - {f}")
    if diagnostic is not None:
        try:
            rel = diagnostic.relative_to(REPO_ROOT)
            print(f"            → {rel}")
        except ValueError:
            print(f"            → {diagnostic}")
    if verbose and r.response:
        preview = r.response.replace("\n", " ")[:200]
        print(f"            response: {preview}")
        if r.tool_names:
            print(f"            tools: {r.tool_names}")


def _dispatch_behavioral(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m evals", description="Scout behavioral evals")
    p.add_argument("--case", help="Run only this case id")
    p.add_argument("--live", action="store_true", help="Run via SSE against a running scout-api")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--verbose", action="store_true", help="Show response + tool previews")
    args = p.parse_args(argv)

    cases = [get(args.case)] if args.case else list(CASES)
    results: list[CaseResult] = []
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {case.id}  {case.prompt[:60]!r}")
        r = run_case(case, live=args.live, base_url=args.base_url)
        diag = write_diagnostic(case, r) if r.status == "FAIL" else None
        _print_case(r, diag, args.verbose)
        results.append(r)

    _print_summary(results)
    return 1 if any(r.status in ("FAIL", "ERROR") for r in results) else 0


def _print_summary(results: list[CaseResult]) -> None:
    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "FAIL", "ERROR", "SKIPPED")}
    total_s = round(sum(r.duration_s for r in results), 1)
    bar = "=" * 60
    print(f"\n{bar}")
    print(
        f"{counts['PASS']} passed, {counts['FAIL']} failed, "
        f"{counts['ERROR']} errored, {counts['SKIPPED']} skipped  ({total_s}s)"
    )
    print(f"{bar}\n")


# ---------------------------------------------------------------------------
# Wiring dispatch
# ---------------------------------------------------------------------------


def _dispatch_wiring(argv: list[str]) -> int:
    from evals.wiring import run_all

    p = argparse.ArgumentParser(prog="python -m evals wiring", description="Scout wiring invariants")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    results = run_all(verbose=args.verbose)
    for r in results:
        tag = _tag("PASS" if r.passed else "FAIL")
        print(f"[{tag}] {r.id} {r.name}")
        if not r.passed:
            print(f"            - {r.detail}")
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    bar = "=" * 60
    print(f"\n{bar}\nwiring: {passed} passed, {failed} failed\n{bar}\n")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Judges dispatch
# ---------------------------------------------------------------------------


def _dispatch_judges(argv: list[str]) -> int:
    from evals.judges import JUDGED, run_all_judged

    p = argparse.ArgumentParser(prog="python -m evals judges", description="Scout judged-quality tier")
    p.add_argument("--case", help="Run only this judged case id")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    results = run_all_judged(case_id=args.case)
    for r in results:
        score = f" score={r.score}" if r.score is not None else ""
        print(f"[{_tag(r.status)}] {r.id:<40} ({r.duration_s:.1f}s){score}")
        if r.reason and r.status != "PASS":
            print(f"            reason: {r.reason[:200]}")
        for f in r.failures:
            print(f"            - {f}")
        if args.verbose and r.response:
            preview = r.response.replace("\n", " ")[:200]
            print(f"            response: {preview}")

    total = len(results) if not args.case else len(JUDGED)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status in ("FAIL", "ERROR"))
    bar = "=" * 60
    print(f"\n{bar}\njudges: {passed}/{total} passed, {failed} failed\n{bar}\n")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "wiring":
        return _dispatch_wiring(argv[1:])
    if argv and argv[0] == "judges":
        return _dispatch_judges(argv[1:])
    return _dispatch_behavioral(argv)


if __name__ == "__main__":
    sys.exit(main())
