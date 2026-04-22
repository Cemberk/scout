"""Evaluate answer quality via LLM-as-judge.

Graders the behavioral tier can't express — answer quality, routing
clarity. Each case scores 0–10 via ``AgentAsJudgeEval``; pass threshold
is ``passing_score`` on the ``Judged`` dataclass (default 7.0).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Literal

from agno.eval.agent_as_judge import AgentAsJudgeEval

from evals.runner import build_fixture, install_fixture, restore_contexts
from scout.settings import default_model

JUDGE_MODEL = default_model()


@dataclass(frozen=True)
class Judged:
    """One judged case."""

    id: str
    prompt: str
    criteria: str
    scoring: Literal["binary", "numeric"] = "numeric"
    passing_score: float = 7.0
    fixture: str = "default"


JUDGED: tuple[Judged, ...] = (
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
    ),
    Judged(
        id="gdrive_citation_quality",
        prompt="Find a Google Drive file about the Q4 roadmap and tell me what it is.",
        criteria=(
            "Score 1-10. The stub Drive context returned exactly one file: "
            "'Q4 Roadmap 2026.gdoc' at https://drive.google.com/file/d/1eval_stub/view. "
            "Points: "
            "(+4) the response names the file (any recognizable form of "
            "'Q4 Roadmap 2026'); "
            "(+3) the response includes the webViewLink or a drive.google.com URL "
            "that's traceable to the stub (file id `1eval_stub` or the full link); "
            "(+2) the response does NOT fabricate content beyond what the stub returned "
            "(no invented authors, no invented body text, no made-up dates other "
            "than what the stub implies); "
            "(+1) the answer is focused — one file, not a padded list of hypotheticals."
        ),
    ),
    Judged(
        id="multi_provider_citation_quality",
        prompt=(
            "What do we know about the Q4 roadmap? Check Slack and Drive, "
            "and cite your sources distinctly."
        ),
        criteria=(
            "Score 1-10. The stub contexts return exactly: "
            "Slack → '#eng-roadmap' finalized 2026-03-11 (permalink on example.slack.com); "
            "Drive → 'Q4 Roadmap 2026.gdoc' at drive.google.com/file/d/1eval_stub/view. "
            "Points: "
            "(+3) both sources are cited and clearly distinguished (not blended); "
            "(+3) the Slack citation includes channel name '#eng-roadmap' OR the "
            "2026-03-11 date, AND the Drive citation includes the file name "
            "or the drive.google.com URL; "
            "(+2) no fabricated facts (no invented owners, no made-up status updates "
            "beyond 'finalized 2026-03-11'); "
            "(+2) the response is structured and scannable (bulleted or sectioned "
            "per source), not a single paragraph of prose."
        ),
    ),
)


JUDGED_BY_ID: dict[str, Judged] = {j.id: j for j in JUDGED}


@dataclass
class JudgedResult:
    id: str
    status: Literal["PASS", "FAIL", "ERROR"]
    duration_s: float
    score: float | None = None
    reason: str = ""
    response: str = ""
    failures: list[str] = field(default_factory=list)


def run_judged(case: Judged) -> JudgedResult:
    """Run one judged case."""
    import uuid

    from scout.team import scout as team

    prev = install_fixture(build_fixture(case.fixture))

    start = time.monotonic()
    try:
        # Fresh session per case so prior runs' history doesn't leak in.
        # Team has `add_history_to_context=True, num_history_runs=5`, and
        # agno reuses session_id when not passed — causing cross-case drift.
        session_id = f"eval-judge-{case.id}-{uuid.uuid4().hex[:8]}"
        run_result = asyncio.run(team.arun(case.prompt, session_id=session_id))
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
