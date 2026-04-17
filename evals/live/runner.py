"""Run one case, assert expectations, write a diagnostic on failure.

On FAIL the diagnostic markdown is written to RESULTS_DIR/<case_id>.md
so scripts/eval_loop.sh can hand it to `claude -p` without re-running
the case. One execution, one artifact, one edit, retry.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from evals.live.cases import REPO_ROOT, EvalCase
from evals.live.client import RunResult, run_team

Status = Literal["PASS", "FAIL", "SKIPPED", "ERROR"]

RESULTS_DIR = REPO_ROOT / "evals" / "results"
DOCKER_SERVICE = "scout-api"


@dataclass
class CaseResult:
    case_id: str
    status: Status
    duration_s: float
    failures: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


# ---------------------------------------------------------------------------
# Execution + assertions
# ---------------------------------------------------------------------------


def run_case(case: EvalCase, *, base_url: str) -> tuple[CaseResult, RunResult | None]:
    """Execute a case and return (CaseResult, RunResult | None)."""
    missing = [var for var in case.requires if not os.environ.get(var)]
    if missing:
        return (
            CaseResult(
                case_id=case.id,
                status="SKIPPED",
                duration_s=0.0,
                skipped_reason=f"missing env vars: {missing}",
            ),
            None,
        )

    try:
        run = run_team(case.prompt, base_url=base_url, timeout_s=case.max_duration_s + 30)
    except Exception as exc:
        return (
            CaseResult(
                case_id=case.id,
                status="ERROR",
                duration_s=0.0,
                failures=[f"{type(exc).__name__}: {exc}"],
            ),
            None,
        )

    failures: list[str] = []

    if run.errors:
        failures.extend(f"run error: {e}" for e in run.errors)

    if run.duration_s > case.max_duration_s:
        failures.append(f"duration {run.duration_s:.1f}s > max {case.max_duration_s}s")

    # Routing
    delegated = [m.get("agent_id") for m in run.member_responses]
    if case.expected_agent is None:
        if run.member_responses:
            failures.append(f"leader should answer directly but delegated to: {delegated}")
    elif case.expected_agent not in delegated:
        failures.append(
            f"expected_agent={case.expected_agent!r} not in {delegated or 'no delegations'}"
        )

    # Response substrings
    lower = (run.final_content or "").lower()
    for needle in case.response_contains:
        if needle.lower() not in lower:
            failures.append(f"missing substring {needle!r}")
    for antineedle in case.response_forbids:
        if antineedle.lower() in lower:
            failures.append(f"forbidden substring present: {antineedle!r}")

    # Tool-call expectations
    tool_names = [tc.get("tool_name") for tc in run.tool_calls]
    for required in case.expected_tools:
        if required not in tool_names:
            failures.append(f"expected tool {required!r} not called; saw {tool_names}")
    for forbidden in case.forbidden_tools:
        if forbidden in tool_names:
            failures.append(f"forbidden tool {forbidden!r} was called")

    return (
        CaseResult(
            case_id=case.id,
            status="PASS" if not failures else "FAIL",
            duration_s=run.duration_s,
            failures=failures,
        ),
        run,
    )


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------


def write_diagnostic(case: EvalCase, result: CaseResult, run: RunResult | None) -> Path:
    """Write a markdown diagnostic for a failed case. Returns the path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{case.id}.md"
    path.write_text(_build_diagnostic(case, result, run))
    return path


def _build_diagnostic(case: EvalCase, result: CaseResult, run: RunResult | None) -> str:
    try:
        instructions = case.target_file.read_text()
    except OSError as exc:
        instructions = f"(could not read {case.target_file}: {exc})"

    parts: list[str] = []
    parts.append(f"# Eval failure: {case.id}")
    parts.append("")
    parts.append(f"Status **{result.status}** — duration {result.duration_s:.1f}s")
    parts.append("")

    parts.append("## Case")
    parts.append(f"- prompt: `{case.prompt}`")
    parts.append(f"- expected_agent: `{case.expected_agent}`")
    parts.append(f"- response_contains: `{case.response_contains}`")
    parts.append(f"- response_forbids: `{case.response_forbids}`")
    parts.append(f"- expected_tools: `{case.expected_tools}`")
    parts.append(f"- forbidden_tools: `{case.forbidden_tools}`")
    parts.append(f"- target_file: `{case.target_file.relative_to(REPO_ROOT)}`")
    parts.append("")

    parts.append("## Failures")
    for f in result.failures or ["(none)"]:
        parts.append(f"- {f}")
    parts.append("")

    if run is not None:
        parts.append("## Actual response")
        parts.append(f"- run_id: `{run.run_id}`")
        parts.append(f"- errors: `{run.errors}`")
        parts.append("")
        parts.append("### Member responses")
        if run.member_responses:
            for m in run.member_responses:
                parts.append(f"**{m.get('agent_id') or '?'}**")
                parts.append("````")
                parts.append(str(m.get("content") or ""))
                parts.append("````")
        else:
            parts.append("(none — leader answered directly)")
        parts.append("")
        parts.append("### Tool calls")
        if run.tool_calls:
            for tc in run.tool_calls:
                args = json.dumps(tc.get("arguments"), default=str)[:200]
                err = tc.get("error")
                line = f"- `{tc.get('tool_name')}` agent=`{tc.get('agent_id')}` args={args}"
                if err:
                    line += f"  ERROR={err}"
                parts.append(line)
        else:
            parts.append("(no tool calls)")
        parts.append("")
        parts.append("### Final content")
        parts.append("````")
        parts.append(run.final_content or "(empty)")
        parts.append("````")
        parts.append("")

    parts.append("## Docker logs (last 200 lines)")
    parts.append("````")
    parts.append(_capture_logs())
    parts.append("````")
    parts.append("")

    parts.append(f"## Current instruction file: `{case.target_file.relative_to(REPO_ROOT)}`")
    parts.append("````python")
    parts.append(instructions)
    parts.append("````")
    parts.append("")

    parts.append("## Instruction to Claude Code")
    parts.append(
        f"Diagnose why this case failed. Edit only `{case.target_file.relative_to(REPO_ROOT)}` "
        "to fix the root cause. Keep changes minimal and spec-aligned "
        "(see tmp/spec.md). Do not run any commands — the harness reruns the case."
    )
    return "\n".join(parts)


def _capture_logs() -> str:
    """Grab `docker compose logs` for the api service. Never raises."""
    try:
        r = subprocess.run(
            ["docker", "compose", "logs", "--no-color", "--tail", "200", DOCKER_SERVICE],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "(docker compose not installed)"
    except subprocess.TimeoutExpired:
        return "(docker compose logs timed out)"
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return out or "(no logs captured)"
