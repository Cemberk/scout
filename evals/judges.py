"""Evaluate answer quality via LLM-as-judge.

Graders the behavioral tier can't express — answer quality, citation
discipline, routing clarity. Cases marked ``fixture="real"`` run
against env-built contexts and hit live providers; cases marked
``fixture="default"`` run against the stub.

Each case scores 0–10 via ``AgentAsJudgeEval``; pass threshold is
``passing_score`` on the ``Judged`` dataclass (default 7.0).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from agno.eval.agent_as_judge import AgentAsJudgeEval
from agno.models.openai import OpenAIResponses

from evals.runner import build_fixture, install_fixture, restore_contexts

JUDGE_MODEL = OpenAIResponses(id="gpt-5.4")


@dataclass(frozen=True)
class Judged:
    """One judged case."""

    id: str
    prompt: str
    criteria: str
    scoring: Literal["binary", "numeric"] = "numeric"
    passing_score: float = 7.0
    fixture: str = "real"
    max_duration_s: int = 240


JUDGED: tuple[Judged, ...] = (
    Judged(
        id="grounded_url_summary",
        prompt=(
            "What does the web context say about the Agno framework? "
            "Use https://docs.agno.com as the primary source. Be specific."
        ),
        criteria=(
            "Score 1-10. Points: "
            "(+5) the answer names concrete Agno features from docs.agno.com — "
            "agents, teams, tools, knowledge, memory, workflows, or similar real primitives; "
            "(+3) the answer cites at least one URL that sits under docs.agno.com; "
            "(+2) the answer is free of obvious hallucination — no invented product names "
            "or features that aren't actually part of Agno."
        ),
    ),
    Judged(
        id="capabilities_clarity",
        prompt="What can you do? Explain in 2-3 sentences.",
        criteria=(
            "Score 1-10. Points: "
            "(+4) both specialists are named — Explorer, Engineer; "
            "(+3) each specialist's role is described concretely (not generic handwaving); "
            "(+2) the answer is concise (roughly 2-3 sentences, not a long essay); "
            "(+1) the answer does NOT promise features Scout doesn't have — no wiki, "
            "slack, gmail, drive, email sending, calendar."
        ),
        fixture="default",
    ),
    Judged(
        id="citation_discipline",
        prompt=(
            "Research one interesting recent fact about LLM evaluation practices "
            "(e.g. benchmarks, judge reliability, eval harnesses). Cite your source."
        ),
        criteria=(
            "Score 1-10. Points: "
            "(+4) at least one specific real URL is cited — not example.com, not a placeholder, "
            "not a bare domain; "
            "(+3) the cited URL corresponds to a specific factual claim in the answer, not just "
            "tacked on at the end; "
            "(+3) the answer is substantive — it delivers a concrete fact, not just "
            "'here's a link'."
        ),
    ),
)


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

    prev = install_fixture(build_fixture(case.fixture))

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
        restore_contexts(prev)


def run_all_judged(case_id: str | None = None) -> list[JudgedResult]:
    """Run every judged case (or one if case_id given)."""
    selected = [JUDGED_BY_ID[case_id]] if case_id else list(JUDGED)
    return [run_judged(c) for c in selected]
