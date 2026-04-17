"""
Eval Runner
===========

Unified runner for all Scout eval categories.

Usage:
    python -m evals
    python -m evals --category routing
    python -m evals --verbose
"""

from __future__ import annotations

import argparse
import importlib
import os
import time
from typing import Literal

from agno.eval.accuracy import AccuracyEval
from agno.eval.agent_as_judge import AgentAsJudgeEval
from agno.eval.reliability import ReliabilityEval

from evals import CATEGORIES, JUDGE_MODEL

# ---------------------------------------------------------------------------
# Result dict shape: {question, category, status, duration, reason?}
# ---------------------------------------------------------------------------


def _get_team():
    """Lazy import to avoid loading the team until needed."""
    from scout.team import scout

    return scout


# ---------------------------------------------------------------------------
# Runners (one per eval type)
# ---------------------------------------------------------------------------


def run_judge_cases(
    cases: list[str],
    criteria: str,
    category: str,
    scoring: Literal["numeric", "binary"],
    verbose: bool = False,
) -> list[dict]:
    """Run AgentAsJudgeEval cases (binary or numeric)."""
    team = _get_team()
    judge = AgentAsJudgeEval(
        name=f"Scout {category}",
        criteria=criteria,
        scoring_strategy=scoring,
        model=JUDGE_MODEL,
    )

    results: list[dict] = []
    for i, question in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] {category}: {question[:60]}...")
        start = time.time()
        try:
            run_result = team.run(question)
            response = run_result.content or ""
            duration = round(time.time() - start, 2)

            eval_result = judge.run(input=question, output=response)
            passed = eval_result is not None and eval_result.pass_rate == 1.0

            result: dict = {
                "question": question,
                "category": category,
                "status": "PASS" if passed else "FAIL",
                "duration": duration,
            }
            if not passed and eval_result and eval_result.results:
                result["reason"] = eval_result.results[0].reason
            if verbose:
                result["response_preview"] = response[:200]
        except Exception as e:
            result = {
                "question": question,
                "category": category,
                "status": "ERROR",
                "reason": str(e),
                "duration": round(time.time() - start, 2),
            }
        results.append(result)
        _print_status(result, verbose)
    return results


def run_reliability_cases(
    cases: list[dict],
    category: str,
    verbose: bool = False,
) -> list[dict]:
    """Run ReliabilityEval cases (expected tool calls)."""
    team = _get_team()
    results: list[dict] = []

    for i, case in enumerate(cases, 1):
        question = case["input"]
        expected_tools = case["expected_tools"]
        print(f"  [{i}/{len(cases)}] {category}: {question[:60]}...")
        start = time.time()
        try:
            run_result = team.run(question)
            duration = round(time.time() - start, 2)

            eval_result = ReliabilityEval(
                name=f"Routing: {question[:40]}",
                team_response=run_result,
                expected_tool_calls=expected_tools,
            ).run()

            passed = eval_result is not None and eval_result.eval_status == "PASSED"
            result: dict = {
                "question": question,
                "category": category,
                "status": "PASS" if passed else "FAIL",
                "duration": duration,
            }
            if not passed and eval_result:
                result["reason"] = f"expected {expected_tools}, failed: {eval_result.failed_tool_calls}"
        except Exception as e:
            result = {
                "question": question,
                "category": category,
                "status": "ERROR",
                "reason": str(e),
                "duration": round(time.time() - start, 2),
            }
        results.append(result)
        _print_status(result, verbose)
    return results


def run_accuracy_cases(
    cases: list[dict],
    category: str,
    verbose: bool = False,
) -> list[dict]:
    """Run AccuracyEval cases (expected output comparison)."""
    team = _get_team()
    results: list[dict] = []

    for i, case in enumerate(cases, 1):
        question = case["input"]
        expected = case["expected_output"]
        guidelines = case.get("guidelines")
        print(f"  [{i}/{len(cases)}] {category}: {question[:60]}...")
        start = time.time()
        try:
            run_result = team.run(question)
            response = run_result.content or ""
            duration = round(time.time() - start, 2)

            eval_obj = AccuracyEval(
                name=f"Knowledge: {question[:40]}",
                input=question,
                expected_output=expected,
                model=JUDGE_MODEL,
                additional_guidelines=guidelines,
            )
            eval_result = eval_obj.run_with_output(output=response)

            passed = eval_result is not None and eval_result.avg_score >= 7.0
            result: dict = {
                "question": question,
                "category": category,
                "status": "PASS" if passed else "FAIL",
                "duration": duration,
            }
            if eval_result and eval_result.results:
                result["score"] = eval_result.results[0].score
                if not passed:
                    result["reason"] = eval_result.results[0].reason
            if verbose:
                result["response_preview"] = response[:200]
        except Exception as e:
            result = {
                "question": question,
                "category": category,
                "status": "ERROR",
                "reason": str(e),
                "duration": round(time.time() - start, 2),
            }
        results.append(result)
        _print_status(result, verbose)
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_status(result: dict, verbose: bool) -> None:
    icon = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERR ", "SKIP": "SKIP"}[result["status"]]
    score = f" (score: {result['score']})" if "score" in result else ""
    print(f"         {icon} ({result['duration']}s){score}")
    if verbose and result.get("reason"):
        print(f"         Reason: {result['reason']}")


def _missing_env(module) -> list[str]:
    """Return the list of env vars the module needs that are unset."""
    required = getattr(module, "SKIP_IF_MISSING", ())
    return [v for v in required if not os.getenv(v)]


def _skip_results(cases, category: str, missing: list[str]) -> list[dict]:
    """Emit SKIP-status dicts for each case when env is missing."""
    skipped: list[dict] = []
    reason = f"skipped — missing env: {', '.join(missing)}"
    for case in cases:
        question = case["input"] if isinstance(case, dict) else case
        skipped.append(
            {
                "question": question,
                "category": category,
                "status": "SKIP",
                "reason": reason,
                "duration": 0.0,
            }
        )
    return skipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

RUNNERS = {
    "judge_binary": lambda mod, cat, v: run_judge_cases(mod.CASES, mod.CRITERIA, cat, "binary", v),
    "judge_numeric": lambda mod, cat, v: run_judge_cases(mod.CASES, mod.CRITERIA, cat, "numeric", v),
    "reliability": lambda mod, cat, v: run_reliability_cases(mod.CASES, cat, v),
    "accuracy": lambda mod, cat, v: run_accuracy_cases(mod.CASES, cat, v),
}


def run_evals(category: str | None = None, verbose: bool = False) -> None:
    """Run eval categories and display results."""
    all_results: list[dict] = []
    total_start = time.time()

    for name, config in CATEGORIES.items():
        if category and name != category:
            continue

        module = importlib.import_module(config["module"])
        case_count = len(module.CASES)

        # Spec §13: env-dependent categories skip, not fail, when env is
        # absent. Each case module may declare `SKIP_IF_MISSING` — if any
        # of those env vars are unset we emit SKIP results and move on.
        missing_env = _missing_env(module)
        if missing_env:
            print(f"\n--- {name} ({case_count} cases) ---  SKIP ({', '.join(missing_env)} not set)\n")
            all_results.extend(_skip_results(module.CASES, name, missing_env))
            continue

        print(f"\n--- {name} ({case_count} cases) ---\n")

        runner = RUNNERS[config["type"]]
        all_results.extend(runner(module, name, verbose))

    if not all_results:
        print(f"No cases found for category: {category}")
        return

    # Summary
    total_duration = round(time.time() - total_start, 2)
    passed = sum(1 for r in all_results if r["status"] == "PASS")
    failed = sum(1 for r in all_results if r["status"] == "FAIL")
    errors = sum(1 for r in all_results if r["status"] == "ERROR")
    skipped = sum(1 for r in all_results if r["status"] == "SKIP")

    print(f"\n{'=' * 50}")
    print(
        f"Results: {passed} passed, {failed} failed, {errors} errors, "
        f"{skipped} skipped ({total_duration}s)"
    )
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Scout evals")
    parser.add_argument("--category", type=str, choices=list(CATEGORIES.keys()), help="Run a single category")
    parser.add_argument("--verbose", action="store_true", help="Show response previews and failure reasons")
    args = parser.parse_args()
    run_evals(category=args.category, verbose=args.verbose)
