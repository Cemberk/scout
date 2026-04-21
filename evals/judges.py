"""LLM-scored quality evals.

Empty for now. New judged cases will land here as the provider set
expands — e.g. grounded-answer quality, citation coverage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from agno.eval.agent_as_judge import AgentAsJudgeEval
from agno.models.openai import OpenAIResponses

from evals.runner import _build_fixture, _install_fixture, _restore

JUDGE_MODEL = OpenAIResponses(id="gpt-5.4")


@dataclass(frozen=True)
class Judged:
    """One judged case."""

    id: str
    prompt: str
    criteria: str
    scoring: Literal["binary", "numeric"]
    passing_score: float = 7.0
    fixture: str = "default"
    max_duration_s: int = 240


JUDGED: tuple[Judged, ...] = ()


JUDGED_BY_ID: dict[str, Judged] = {j.id: j for j in JUDGED}


@dataclass
class JudgedResult:
    id: str
    status: Literal["PASS", "FAIL", "ERROR", "SKIPPED"]
    duration_s: float
    score: float | None = None
    reason: str = ""
    response: str = ""
    failures: list[str] = field(default_factory=list)


def run_judged(case: Judged) -> JudgedResult:
    """Run one judged case."""
    from scout.team import scout as team

    class _FakeCase:
        def __init__(self, fixture: str) -> None:
            self.fixture = fixture

    fixture = _build_fixture(_FakeCase(case.fixture))  # type: ignore[arg-type]
    prev = _install_fixture(fixture)

    start = time.monotonic()
    try:
        run_result = team.run(case.prompt)
        response = getattr(run_result, "content", None) or ""
        duration = time.monotonic() - start

        judge = AgentAsJudgeEval(
            name=f"scout-judged-{case.id}",
            criteria=case.criteria,
            scoring_strategy=case.scoring,
            model=JUDGE_MODEL,
        )
        eval_result = judge.run(input=case.prompt, output=response)

        if eval_result is None or not eval_result.results:
            return JudgedResult(
                id=case.id,
                status="ERROR",
                duration_s=duration,
                response=response,
                failures=["judge returned no result"],
            )

        first = eval_result.results[0]
        if case.scoring == "binary":
            passed_flag = bool(getattr(first, "passed", False))
            score_val: float | None = None
            fail_msg = "judge returned passed=False"
        else:
            raw_score = getattr(first, "score", None)
            score_val = float(raw_score) if raw_score is not None else 0.0
            passed_flag = score_val >= case.passing_score
            fail_msg = f"score {score_val} < threshold {case.passing_score}"
        return JudgedResult(
            id=case.id,
            status="PASS" if passed_flag else "FAIL",
            duration_s=duration,
            score=score_val,
            reason=str(getattr(first, "reason", "")),
            response=response,
            failures=[] if passed_flag else [fail_msg],
        )
    except Exception as exc:
        return JudgedResult(
            id=case.id,
            status="ERROR",
            duration_s=time.monotonic() - start,
            failures=[f"{type(exc).__name__}: {exc}"],
        )
    finally:
        _restore(prev)
        if fixture.teardown:
            try:
                fixture.teardown()
            except Exception:
                pass


def run_all_judged(case_id: str | None = None) -> list[JudgedResult]:
    """Run every judged case (or one if case_id given)."""
    selected = [JUDGED_BY_ID[case_id]] if case_id else list(JUDGED)
    return [run_judged(c) for c in selected]


__all__ = ["JUDGED", "JUDGED_BY_ID", "Judged", "JudgedResult", "run_all_judged", "run_judged"]
