"""
Scout Autonomous Improve Loop
==============================

Runs one or more eval tiers, feeds failures to GPT-5.4, applies bounded
edits to a whitelisted file surface, validates, re-runs, and rolls back
on regression. Commits each non-regression round.

Adapted from dash/evals/improve.py. Scout differences:
- Three tiers (smoke / live / static), not just smoke.
- Wider edit whitelist — instructions + every agent + team.py + tools/build.py.
- Commits per round (user decision) so history shows each convergence step.

Usage:
    python -m evals improve
    python -m evals improve --tier smoke --rounds 2
    python -m evals improve --dry-run --verbose
    python -m evals improve --no-commit
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Paths — the ONLY files the loop may modify
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCOUT_DIR = REPO_ROOT / "scout"

ALLOWED_FILES: dict[str, Path] = {
    "scout/instructions.py": REPO_ROOT / "scout/instructions.py",
    "scout/team.py": REPO_ROOT / "scout/team.py",
    "scout/agents/navigator.py": REPO_ROOT / "scout/agents/navigator.py",
    "scout/agents/compiler.py": REPO_ROOT / "scout/agents/compiler.py",
    "scout/agents/code_explorer.py": REPO_ROOT / "scout/agents/code_explorer.py",
    "scout/agents/engineer.py": REPO_ROOT / "scout/agents/engineer.py",
    "scout/agents/doctor.py": REPO_ROOT / "scout/agents/doctor.py",
    "scout/tools/build.py": REPO_ROOT / "scout/tools/build.py",
}

RESULTS_DIR = REPO_ROOT / "evals/results"

Tier = Literal["smoke", "live", "static", "all"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Change:
    file: str  # key in ALLOWED_FILES
    old_text: str
    new_text: str
    rationale: str


@dataclass
class ImprovementPlan:
    analysis: str
    changes: list[Change] = field(default_factory=list)


@dataclass
class RoundReport:
    round_number: int
    before_pass: int
    before_fail: int
    after_pass: int
    after_fail: int
    analysis: str
    changes_applied: list[str]
    regressions: list[str]
    duration: float
    commit_sha: str | None = None


# ---------------------------------------------------------------------------
# Analyzer system prompt — canonical, lives here (not in tmp/)
# ---------------------------------------------------------------------------

ANALYZER_SYSTEM_PROMPT = """\
You are a prompt engineer improving Scout, an enterprise context agent. You
are NOT running tests — you are reading failing test results and proposing
minimal, exact-match string edits that will make them pass without breaking
anything that already passes.

Scout architecture (ground truth — do not contradict):
- Leader coordinates five specialists: Navigator (read-only), Compiler (owns
  wiki writes), CodeExplorer (clone + read repos), Engineer (owns SQL writes
  into scout_* tables), Doctor (self-diagnosis + self-heal).
- Three write paths: context/raw + context/compiled -> Compiler; scout_*
  tables -> Engineer; outbound (Slack post, Gmail send, Calendar write) ->
  Leader. Everything else reads.

Editable surface (you may ONLY propose edits to these files):
- scout/instructions.py — shared BASE_INSTRUCTIONS + web/email/calendar voice
- scout/team.py — Leader routing rules (LEADER_INSTRUCTIONS)
- scout/agents/navigator.py — Navigator's role-specific instructions
- scout/agents/compiler.py — Compiler's ingest/compile/lint instructions
- scout/agents/code_explorer.py — CodeExplorer's clone + read playbook
- scout/agents/engineer.py — Engineer's write discipline (scout schema only)
- scout/agents/doctor.py — Doctor's diagnose/self-heal playbook
- scout/tools/build.py — which tools bind to which agent

Never propose edits to: evals/, scout/manifest.py, scout/sources/,
scout/compile/, scout/tools/sources.py, scout/tools/ingest.py, context/,
db/, app/, tmp/.

Failure -> dial map:
- Wrong agent routed -> scout/team.py LEADER_INSTRUCTIONS routing table
- Right agent, wrong tool -> that agent's instructions in scout/agents/<name>.py
- Agent called a tool it shouldn't have -> scout/tools/build.py (tool binding)
- Response missing required substring -> tighten the agent's format guidance
- Response leaks forbidden content -> Leader refusal rules or Navigator refusal
- Governance failure -> tool binding in scout/tools/build.py OR agent refusal
  instructions; never propose loosening scout/manifest.py
- Timeout exceeded -> tighten 'when to stop' guidance; never raise the timeout

Invariants you must preserve:
1. `python -m scout _smoke_gating` must exit 0 — Navigator refuses local:raw.
2. Drafts-only Gmail and Calendar unless SCOUT_ALLOW_SENDS=true.
3. Navigator, Doctor, Leader use the read-only SQL engine.
4. No new dependencies, no new agents, no new sources, no new tools.
5. Wiki citations use compiled article paths, never raw paths.
6. SQL scoped to user_id = '{user_id}'.

Out of scope — don't propose even if a test seems to ask:
- A Syncer agent or sync_status/sync_push tools (Scout has 5 specialists).
- Multi-workspace, Notion/SharePoint/Azure/GCS sources, warehouse SQL.
- Article splitting within the Compiler.

How to write a good change:
- Exact match, exactly once. If a phrase repeats, include more context.
- Minimal. Change the smallest unit that fixes the failure.
- Don't break Python syntax (loop compiles + rolls back on SyntaxError).
- Don't hardcode answers to the failing prompt. Fix the pattern.
- Name the test ids in the rationale.

Return exactly this JSON — no prose before or after:
{
  "analysis": "2-3 paragraphs: which failures cluster, root cause, what the changes do at a system level. Name test ids.",
  "changes": [
    {
      "file": "scout/agents/navigator.py",
      "old_text": "literal string already in the file (exactly once)",
      "new_text": "replacement — minimal, preserves syntax",
      "rationale": "which test id(s) this fixes and why"
    }
  ]
}

If no safe change is possible, return {"analysis": "...", "changes": []}.
"""


# ---------------------------------------------------------------------------
# Tier runners — unified interface: list[(id, status, prompt, failures, response)]
# ---------------------------------------------------------------------------


@dataclass
class TierResult:
    id: str
    status: str
    prompt: str
    failures: list[str]
    response: str


def _run_smoke_tier() -> list[TierResult]:
    from evals.smoke import run_smoke_tests

    out: list[TierResult] = []
    for r in run_smoke_tests(verbose=False):
        out.append(
            TierResult(
                id=r.test.id,
                status=r.status,
                prompt=r.test.prompt,
                failures=r.failures,
                response=r.response[:500],
            )
        )
    return out


def _run_live_tier(base_url: str = "http://localhost:8000") -> list[TierResult]:
    """Run live harness. SKIP with a note if the API isn't responsive or imports are broken."""
    # Cheap liveness check first — we don't want the loop to hang if Docker is down.
    try:
        import urllib.request

        urllib.request.urlopen(f"{base_url}/manifest", timeout=2)
    except Exception as exc:
        print(f"  [live tier] API not reachable at {base_url}: {exc}. Skipping.")
        return []

    try:
        from evals.live.cases import CASES as LIVE_CASES
        from evals.live.runner import run_case
    except Exception as exc:
        print(f"  [live tier] import failed ({exc}). Skipping.")
        return []

    out: list[TierResult] = []
    for case in LIVE_CASES:
        try:
            result, run_result = run_case(case, base_url=base_url)
        except Exception as exc:
            out.append(TierResult(id=case.id, status="ERROR", prompt=case.prompt, failures=[str(exc)], response=""))
            continue
        out.append(
            TierResult(
                id=case.id,
                status=result.status,
                prompt=case.prompt,
                failures=list(getattr(result, "failures", []) or []),
                response=(getattr(run_result, "final_content", "") or "")[:500],
            )
        )
    return out


def _run_static_tier() -> list[TierResult]:
    """Static tier — agno judge/reliability/accuracy. Expensive; not default.

    Defensive: if eval-category modules are mid-edit and crash at import,
    we skip that category rather than blowing up the whole loop.
    """
    try:
        from evals import CATEGORIES
        from evals.run import RUNNERS, _missing_env, _skip_results
    except Exception as exc:
        print(f"  [static tier] import failed ({exc}). Skipping.")
        return []

    out: list[TierResult] = []
    for name, config in CATEGORIES.items():
        try:
            module = importlib.import_module(config["module"])
        except Exception as exc:
            print(f"  [static tier] category '{name}' import failed: {exc}")
            continue

        missing = _missing_env(module)
        if missing:
            for d in _skip_results(module.CASES, name, missing):
                out.append(
                    TierResult(
                        id=f"{name}::{d['question'][:40]}",
                        status="SKIP",
                        prompt=d["question"],
                        failures=[d.get("reason", "")],
                        response="",
                    )
                )
            continue
        try:
            runner = RUNNERS[config["type"]]
            for d in runner(module, name, False):
                out.append(
                    TierResult(
                        id=f"{name}::{d['question'][:40]}",
                        status=d["status"],
                        prompt=d["question"],
                        failures=[d.get("reason", "")] if d["status"] != "PASS" else [],
                        response=d.get("response_preview", "")[:500],
                    )
                )
        except Exception as exc:
            print(f"  [static tier] category '{name}' run failed: {exc}")
    return out


def _collect_baseline(tier: Tier) -> list[TierResult]:
    """Run tiers in cost order; return FIRST tier's results that has a failure, or the last tier's.

    Rationale: smoke is cheapest; if it's already failing, there's no point
    running live/static before trying a fix. If smoke is clean, proceed to
    live, etc. When `tier` is a single name we just run that one.
    """
    if tier == "smoke":
        return _run_smoke_tier()
    if tier == "live":
        return _run_live_tier()
    if tier == "static":
        return _run_static_tier()

    # tier == "all"
    smoke = _run_smoke_tier()
    if any(r.status not in ("PASS", "SKIPPED", "SKIP") for r in smoke):
        return smoke
    live = _run_live_tier()
    if any(r.status not in ("PASS", "SKIPPED", "SKIP") for r in live):
        return live
    static = _run_static_tier()
    return static or smoke  # always return something


def _pass_fail(results: list[TierResult]) -> tuple[int, int]:
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status not in ("PASS", "SKIP", "SKIPPED"))
    return passed, failed


def _status_map(results: list[TierResult]) -> dict[str, str]:
    return {r.id: r.status for r in results}


# ---------------------------------------------------------------------------
# LLM analysis
# ---------------------------------------------------------------------------


def _build_analysis_prompt(results: list[TierResult], file_contents: dict[str, str]) -> str:
    failing = [r for r in results if r.status not in ("PASS", "SKIP", "SKIPPED")]
    test_lines = [
        json.dumps(
            {
                "id": r.id,
                "status": r.status,
                "prompt": r.prompt,
                "failures": r.failures,
                "response_preview": r.response,
            }
        )
        for r in failing
    ]

    file_blocks = []
    for name, content in file_contents.items():
        lang = "python" if name.endswith(".py") else ""
        file_blocks.append(f"### {name}\n\n```{lang}\n{content}\n```")

    return f"""## Failing tests ({len(failing)} of {len(results)})

{chr(10).join(test_lines)}

## Editable files

{chr(10).join(file_blocks)}

Analyze the failures. Propose minimal, exact-match string edits that fix the
root cause. Return the JSON contract described in the system prompt.
"""


def _call_analyzer(results: list[TierResult], file_contents: dict[str, str]) -> ImprovementPlan:
    from openai import OpenAI

    client = OpenAI()
    system = ANALYZER_SYSTEM_PROMPT
    user = _build_analysis_prompt(results, file_contents)

    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = json.loads(response.choices[0].message.content or "{}")
    changes: list[Change] = []
    for c in raw.get("changes", []):
        if c.get("file") not in ALLOWED_FILES:
            print(f"    WARNING: analyzer proposed edit to non-whitelisted file: {c.get('file')!r}")
            continue
        changes.append(
            Change(
                file=c["file"],
                old_text=c["old_text"],
                new_text=c["new_text"],
                rationale=c.get("rationale", ""),
            )
        )
    return ImprovementPlan(analysis=raw.get("analysis", ""), changes=changes)


# ---------------------------------------------------------------------------
# Change application
# ---------------------------------------------------------------------------


def _backup(path: Path, round_num: int) -> Path:
    bak = path.with_suffix(path.suffix + f".bak.round-{round_num}")
    shutil.copy2(path, bak)
    return bak


def _restore(path: Path, round_num: int) -> bool:
    bak = path.with_suffix(path.suffix + f".bak.round-{round_num}")
    if bak.exists():
        shutil.copy2(bak, path)
        return True
    return False


def _cleanup_backups(round_num: int) -> None:
    for path in ALLOWED_FILES.values():
        bak = path.with_suffix(path.suffix + f".bak.round-{round_num}")
        if bak.exists():
            try:
                bak.unlink()
            except OSError:
                pass


def apply_changes(changes: list[Change], round_num: int) -> list[str]:
    """Apply a plan's changes. Returns descriptions of what actually landed."""
    applied: list[str] = []
    backed_up: set[str] = set()

    for change in changes:
        path = ALLOWED_FILES[change.file]
        if not path.exists():
            print(f"    WARNING: {change.file} not found, skipping")
            continue

        if change.file not in backed_up:
            _backup(path, round_num)
            backed_up.add(change.file)

        content = path.read_text()
        occurrences = content.count(change.old_text)
        if occurrences == 0:
            print(f"    WARNING: old_text not found in {change.file}: {change.old_text[:80]!r}...")
            continue
        if occurrences > 1:
            print(
                f"    WARNING: old_text occurs {occurrences}x in {change.file} — ambiguous, rejecting. "
                f"Include more context in old_text next round."
            )
            continue

        path.write_text(content.replace(change.old_text, change.new_text, 1))
        applied.append(f"{change.file}: {change.rationale}")

    # Syntax-validate all modified .py files; roll back individually on error.
    for file_key in list(backed_up):
        p = ALLOWED_FILES[file_key]
        if not p.name.endswith(".py"):
            continue
        try:
            compile(p.read_text(), str(p), "exec")
        except SyntaxError as e:
            print(f"    ERROR: {file_key} syntax invalid after edit: {e}")
            print(f"    Rolling back {file_key}")
            _restore(p, round_num)
            applied = [a for a in applied if not a.startswith(f"{file_key}:")]

    return applied


# ---------------------------------------------------------------------------
# Module reload
# ---------------------------------------------------------------------------


def _reload_scout() -> None:
    """Reload scout modules so edited instructions take effect in-process."""
    targets = [
        "scout.instructions",
        "scout.agents.navigator",
        "scout.agents.compiler",
        "scout.agents.code_explorer",
        "scout.agents.engineer",
        "scout.agents.doctor",
        "scout.agents",
        "scout.team",
        "scout",
    ]
    for name in targets:
        mod = importlib.import_module(name)
        importlib.reload(mod)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(*args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return 127, "git not installed"


def _commit_round(report: RoundReport) -> str | None:
    """Stage whitelisted files and commit; return short SHA or None."""
    # Only add files that are actually whitelisted — never `git add -A`.
    for key in ALLOWED_FILES:
        _git("add", "--", key)

    rc, diff = _git("diff", "--cached", "--name-only")
    if rc != 0 or not diff.strip():
        print("    (no staged changes to commit)")
        return None

    delta = report.after_pass - report.before_pass
    head_title = f"improve(round-{report.round_number}): +{delta} tests"
    rationale = "; ".join(c.split(": ", 1)[1] for c in report.changes_applied if ": " in c)[:180]
    body = report.analysis[:500]
    msg = f"{head_title}\n\n{rationale}\n\n---\n{body}"

    rc, out = _git("commit", "-m", msg)
    if rc != 0:
        print(f"    git commit failed: {out}")
        return None
    rc2, sha = _git("rev-parse", "--short", "HEAD")
    return sha.strip() if rc2 == 0 else None


# ---------------------------------------------------------------------------
# Artifact writer
# ---------------------------------------------------------------------------


def _write_artifact(report: RoundReport, results_before: list[TierResult], results_after: list[TierResult]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"improve-round-{report.round_number}.json"
    data = {
        "round": report.round_number,
        "duration_s": report.duration,
        "before": {
            "pass": report.before_pass,
            "fail": report.before_fail,
            "status_map": _status_map(results_before),
        },
        "after": {
            "pass": report.after_pass,
            "fail": report.after_fail,
            "status_map": _status_map(results_after),
        },
        "analysis": report.analysis,
        "changes_applied": report.changes_applied,
        "regressions": report.regressions,
        "commit_sha": report.commit_sha,
    }
    path.write_text(json.dumps(data, indent=2))
    print(f"    artifact: {path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_improvement_loop(
    rounds: int = 3,
    tier: Tier = "smoke",
    dry_run: bool = False,
    verbose: bool = False,
    commit: bool = True,
) -> bool:
    """Run the autonomous improve loop.

    Returns True if the final state has zero failures on the selected tier.
    """
    print(f"\nScout Self-Improvement Loop — tier={tier}, rounds={rounds}{' (dry run)' if dry_run else ''}")
    print("=" * 60)

    for round_num in range(1, rounds + 1):
        round_start = time.time()
        print(f"\n{'=' * 60}")
        print(f"ROUND {round_num}/{rounds}")
        print(f"{'=' * 60}")

        # 1. Baseline
        print("\n  Running baseline...")
        before = _collect_baseline(tier)
        before_pass, before_fail = _pass_fail(before)
        before_map = _status_map(before)

        if before_fail == 0:
            print(f"\n  All {before_pass} tests passing on '{tier}' tier. No improvements needed.")
            return True

        print(f"\n  Baseline: {before_pass} passed, {before_fail} failing")

        # 2. Read editable surface
        file_contents = {k: p.read_text() for k, p in ALLOWED_FILES.items() if p.exists()}

        # 3. Analyze
        print("  Analyzing with gpt-5.4...")
        plan = _call_analyzer(before, file_contents)

        print("\n  Analysis:")
        for line in plan.analysis.splitlines():
            print(f"    {line}")

        if not plan.changes:
            print("\n  No changes proposed. Stopping.")
            return before_fail == 0

        print(f"\n  Proposed changes ({len(plan.changes)}):")
        for i, c in enumerate(plan.changes, 1):
            print(f"    {i}. [{c.file}] {c.rationale}")
            if verbose:
                print(f"       old: {c.old_text[:120]!r}")
                print(f"       new: {c.new_text[:120]!r}")

        if dry_run:
            print("\n  Dry run — skipping application.\n")
            continue

        # 4. Apply
        print("\n  Applying...")
        applied = apply_changes(plan.changes, round_num)
        if not applied:
            print("  No changes could be applied. Stopping.")
            return before_fail == 0
        for desc in applied:
            print(f"    applied: {desc}")

        # 5. Reload
        print("  Reloading scout modules...")
        try:
            _reload_scout()
        except Exception as e:
            print(f"  ERROR reloading: {e}")
            for key in ALLOWED_FILES:
                _restore(ALLOWED_FILES[key], round_num)
            _reload_scout()
            return False

        # 6. Verify
        print("\n  Running verification...")
        after = _collect_baseline(tier)
        after_pass, after_fail = _pass_fail(after)
        after_map = _status_map(after)

        # 7. Regression check
        regressions = [
            tid for tid, before_status in before_map.items() if before_status == "PASS" and after_map.get(tid) != "PASS"
        ]

        duration = round(time.time() - round_start, 1)
        report = RoundReport(
            round_number=round_num,
            before_pass=before_pass,
            before_fail=before_fail,
            after_pass=after_pass,
            after_fail=after_fail,
            analysis=plan.analysis,
            changes_applied=applied,
            regressions=regressions,
            duration=duration,
        )

        if regressions:
            print(f"\n  REGRESSION in: {', '.join(regressions)}")
            print("  Rolling back all changes this round...")
            for key in ALLOWED_FILES:
                _restore(ALLOWED_FILES[key], round_num)
            _reload_scout()
            _print_round_report(report)
            _write_artifact(report, before, after)
            _cleanup_backups(round_num)
            return False

        # 8. Commit
        if commit:
            report.commit_sha = _commit_round(report)

        _print_round_report(report)
        _write_artifact(report, before, after)
        _cleanup_backups(round_num)

        if after_fail == 0:
            print(f"\n  All tests passing after round {round_num}.")
            return True

    print(f"\n{'=' * 60}")
    print(f"Loop exhausted after {rounds} rounds")
    print(f"{'=' * 60}\n")
    return False


def _print_round_report(report: RoundReport) -> None:
    delta = report.after_pass - report.before_pass
    sign = f"+{delta}" if delta > 0 else str(delta)
    sha = f" [{report.commit_sha}]" if report.commit_sha else ""
    print(f"\n  Round {report.round_number} ({report.duration}s){sha}:")
    print(f"    before: {report.before_pass} passed, {report.before_fail} failing")
    print(f"    after:  {report.after_pass} passed, {report.after_fail} failing ({sign})")
    print(f"    changes applied: {len(report.changes_applied)}")
    if report.regressions:
        print(f"    REGRESSIONS: {', '.join(report.regressions)}")
