"""LLM-scored quality evals — voice + grounded-answer.

Small tier — cap at 10 across all sub-categories. If a case can be
expressed as a deterministic assertion, it belongs in ``cases.py``;
if it truly needs a judge, it lives here.

Voice cases score numerically (≥ 7 passes); answer-quality cases
score binary (1.0 passes). Judge is ``OpenAIResponses(id="gpt-5.4")``.

Cases run in-process via the Scout team with a stub fixture so the
response is grounded in known content — judges evaluate quality, not
retrieval correctness.
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
    passing_score: float = 7.0  # numeric threshold; ignored for binary
    fixture: str = "default"
    max_duration_s: int = 240


# ---------------------------------------------------------------------------
# Voice cases — one per guide
# ---------------------------------------------------------------------------

_VOICE_EMAIL_CRITERIA = (
    "Score 1-10 how well the drafted email matches a concise, direct internal "
    "voice guide: (1) opens with the point, no 'I hope this finds you well' "
    "preamble; (2) short paragraphs, plain language; (3) clear ask or takeaway; "
    "(4) signs off briefly. Penalize corporate filler, nested hedging, and long "
    "intros. Score 7+ means the draft is usable with minor tweaks."
)

_VOICE_SLACK_CRITERIA = (
    "Score 1-10 how well the drafted Slack message matches a terse, informal "
    "tone: (1) ≤ 3 lines unless scope demands more; (2) context before ask; "
    "(3) no 'Hello team' preamble; (4) tag people only if action is required. "
    "Penalize paragraphs and formal register. Score 7+ is usable."
)

_VOICE_DOC_CRITERIA = (
    "Score 1-10 how well the drafted document matches a clear technical "
    "voice: (1) title + one-line summary; (2) sections with headings; (3) "
    "recommendation before rationale; (4) no thesaurus-speak. Penalize "
    "meandering intros and bullet-soup without structure. Score 7+ is usable."
)

# ---------------------------------------------------------------------------
# Answer-quality cases — binary
# ---------------------------------------------------------------------------

_GROUNDED_CRITERIA = (
    "Binary: does the response cite a concrete article path, context id, or "
    "entry identifier that could plausibly come from a registered source? A "
    "response that says 'yes, per the wiki' without naming the article fails. "
    "A response that names a fabricated article (one not matching the fixture) "
    "fails. Correct means at least one grounded citation."
)

_NO_HALLUCINATION_CRITERIA = (
    "Binary: the question asks about an article that doesn't exist. Correct "
    "means the response says it's not in the wiki / not found. Incorrect "
    "means the response invents facts (dates, section numbers, specific "
    "content) about the nonexistent article."
)

_MERGE_DISTINCT_CRITERIA = (
    "Binary: the response references TWO distinct registered contexts and "
    "keeps their answers separate (by source heading, per-context section, "
    "or explicit attribution). Merging into one phantom paraphrased answer "
    "without distinguishing which context said what fails."
)


JUDGED: tuple[Judged, ...] = (
    Judged(
        id="voice_email_draft",
        prompt="Draft an email to the engineering leads about the upcoming architecture review.",
        criteria=_VOICE_EMAIL_CRITERIA,
        scoring="numeric",
        passing_score=7.0,
    ),
    Judged(
        id="voice_slack_draft",
        prompt="Draft a Slack message announcing the Monday 10am planning session.",
        criteria=_VOICE_SLACK_CRITERIA,
        scoring="numeric",
        passing_score=7.0,
    ),
    Judged(
        id="voice_document_draft",
        prompt=(
            "Write a one-page technical document comparing two deployment "
            "strategies (single container vs scheduler-split), with a clear "
            "recommendation."
        ),
        criteria=_VOICE_DOC_CRITERIA,
        scoring="numeric",
        passing_score=7.0,
    ),
    Judged(
        id="answer_grounded_citation",
        prompt="What does the wiki say about onboarding? Cite your source.",
        criteria=_GROUNDED_CRITERIA,
        scoring="binary",
    ),
    Judged(
        id="answer_no_month_hallucination",
        prompt="Summarize our 'Project Chimera Deprecation Plan' — what are the sunset dates?",
        criteria=_NO_HALLUCINATION_CRITERIA,
        scoring="binary",
    ),
    Judged(
        id="answer_merge_distinct_contexts",
        prompt=(
            "Compare what the wiki says about onboarding with what the "
            "sample-local context has on the same topic. Keep them distinct."
        ),
        criteria=_MERGE_DISTINCT_CRITERIA,
        scoring="binary",
    ),
)


JUDGED_BY_ID: dict[str, Judged] = {j.id: j for j in JUDGED}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


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
    """Run one judged case. Installs fixture, runs team, scores via agno."""
    from scout.team import scout as team

    class _FakeCase:
        """Adapter so we can reuse the runner's fixture-install helpers."""

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
        # agno's AgentAsJudgeResult uses different fields per scoring mode:
        #   numeric → .score is a float, .passed is None
        #   binary  → .passed is a bool, .score is None
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
        _restore(*prev)
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
