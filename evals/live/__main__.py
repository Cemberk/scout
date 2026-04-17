"""Scout live-eval CLI.

    python -m evals.live run [--case ID] [--base-url URL]

On failure, a diagnostic is written to evals/results/<case_id>.md.
scripts/eval_loop.sh feeds that file to `claude -p` for autonomous fixing.

Exit codes: 0 = all pass/skipped, 1 = any FAIL or ERROR.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.live.cases import CASES, REPO_ROOT, get
from evals.live.runner import RESULTS_DIR, CaseResult, run_case, write_diagnostic

_COLORS = {"PASS": "\033[32m", "FAIL": "\033[31m", "ERROR": "\033[31m", "SKIPPED": "\033[33m"}
_RESET = "\033[0m"


def _fmt(status: str) -> str:
    if sys.stdout.isatty():
        return f"{_COLORS.get(status, '')}{status:<7}{_RESET}"
    return f"{status:<7}"


def _print(r: CaseResult, diagnostic: Path | None) -> None:
    print(f"[{_fmt(r.status)}] {r.case_id:<28} ({r.duration_s:.1f}s)")
    if r.skipped_reason:
        print(f"            {r.skipped_reason}")
    for f in r.failures:
        print(f"            - {f}")
    if diagnostic:
        print(f"            → {diagnostic.relative_to(REPO_ROOT)}")


def _save_summary(results: list[CaseResult]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"summary-{ts}.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": ts,
                "results": [r.__dict__ for r in results],
            },
            indent=2,
        )
    )
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evals.live", description="Scout live-eval harness")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="Run all cases or a single case")
    p_run.add_argument("--case", help="Run only this case id")
    p_run.add_argument("--base-url", default="http://localhost:8000")
    args = p.parse_args(argv)

    cases = [get(args.case)] if args.case else list(CASES)
    results: list[CaseResult] = []
    for case in cases:
        result, run = run_case(case, base_url=args.base_url)
        diagnostic = write_diagnostic(case, result, run) if result.status == "FAIL" else None
        _print(result, diagnostic)
        results.append(result)

    summary = _save_summary(results)
    print()
    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "FAIL", "ERROR", "SKIPPED")}
    print(
        f"{counts['PASS']} passed, {counts['FAIL']} failed, "
        f"{counts['ERROR']} errored, {counts['SKIPPED']} skipped"
    )
    print(f"summary → {summary.relative_to(REPO_ROOT)}")
    return 0 if counts["FAIL"] == 0 and counts["ERROR"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
