"""Behavioral-case runner — dual transport, fixtures, diagnostics.

One case, two transports: in-process ``team.run()`` by default, or
``POST /teams/scout/runs`` SSE when invoked with ``--live``. The
assertion model is identical; only the execution path differs.

Fixtures are installed per case via
``scout.contexts.set_runtime(contexts)``. In ``--live`` mode the caller
is expected to have set ``PARALLEL_API_KEY`` to match the fixture;
cases that need a specific in-process fixture SKIP with a note.

On FAIL, a self-contained diagnostic is written to
``evals/results/<case_id>.md``.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from evals.cases import REPO_ROOT, Case

Status = Literal["PASS", "FAIL", "SKIPPED", "ERROR"]

RESULTS_DIR = REPO_ROOT / "evals" / "results"
DOCKER_SERVICE = "scout-api"


@dataclass
class CaseResult:
    case_id: str
    status: Status
    duration_s: float
    transport: str = "in-process"
    failures: list[str] = field(default_factory=list)
    skipped_reason: str | None = None
    response: str = ""
    tool_names: list[str] = field(default_factory=list)
    delegated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class Fixture:
    """A list of contexts to install into the runtime registry."""

    contexts: list[Any]


def _stub_context(ctx_id: str, display_name: str, answer_text: str):
    """A ContextProvider subclass with a canned ``query()`` answer."""
    from scout.context.provider import Answer, ContextProvider
    from scout.context.provider import Status as ProviderStatus

    class StubContext(ContextProvider):
        def __init__(self) -> None:
            super().__init__(id=ctx_id, name=display_name)

        def status(self):
            return ProviderStatus(ok=True, detail=f"stub {ctx_id}")

        def query(self, question, *, limit=10):
            del question, limit
            return Answer(text=answer_text)

    return StubContext()


def build_fixture(name: str) -> Fixture:
    """Build a fixture by name. Used by both behavioral and judged runners."""
    if name == "none":
        return Fixture(contexts=[])

    if name == "default":
        return Fixture(
            contexts=[
                _stub_context(
                    "web",
                    "Web (stub)",
                    "Stub web answer for eval purposes. Cited: https://example.com/stub",
                ),
            ]
        )

    if name == "real":
        # Real env-built contexts — hits actual providers. Needs
        # OPENAI_API_KEY plus a backend key (PARALLEL_API_KEY / EXA_API_KEY).
        from scout.contexts import build_contexts

        return Fixture(contexts=build_contexts())

    raise ValueError(f"unknown fixture {name!r}")


def install_fixture(fixture: Fixture) -> list[Any]:
    """Install the fixture via ``set_runtime``. Returns the prior contexts."""
    from scout.contexts import get_contexts, set_runtime

    prev_contexts = get_contexts()
    set_runtime(fixture.contexts)
    return prev_contexts


def restore_contexts(prev_contexts: list[Any]) -> None:
    from scout.contexts import set_runtime

    set_runtime(prev_contexts)


# ---------------------------------------------------------------------------
# Transport — in-process
# ---------------------------------------------------------------------------


def _extract_in_process(run_result: Any) -> tuple[str, list[str], list[str], list[str]]:
    """Pull (content, tool_names, delegated_agent_ids, errors) from a TeamRunOutput."""
    content = getattr(run_result, "content", None) or ""
    tools: list[str] = []
    delegated: list[str] = []
    errors: list[str] = []

    def _names_from(obj: Any) -> list[str]:
        out: list[str] = []
        t_list = getattr(obj, "tools", None)
        if not isinstance(t_list, (list, tuple)):
            return out
        for t in t_list:
            if isinstance(t, dict):
                n = t.get("tool_name") or t.get("name")
                err = t.get("error")
                if n:
                    out.append(str(n))
                if err:
                    errors.append(str(err))
                continue
            n = (
                getattr(t, "tool_name", None)
                or getattr(t, "name", None)
                or getattr(getattr(t, "function", None), "name", None)
            )
            if n:
                out.append(str(n))
            err = getattr(t, "error", None)
            if err:
                errors.append(str(err))
        return out

    tools.extend(_names_from(run_result))

    members = getattr(run_result, "member_responses", None)
    if isinstance(members, (list, tuple)):
        for m in members:
            aid = getattr(m, "agent_id", None) or (m.get("agent_id") if isinstance(m, dict) else None)
            if aid:
                delegated.append(str(aid))
            tools.extend(_names_from(m))

    return content, tools, delegated, errors


def _run_in_process(case: Case) -> tuple[str, list[str], list[str], list[str], float]:
    from scout.team import scout as team

    start = time.monotonic()
    run_result = team.run(case.prompt)
    duration = time.monotonic() - start
    content, tools, delegated, errors = _extract_in_process(run_result)
    return content, tools, delegated, errors, duration


# ---------------------------------------------------------------------------
# Transport — live SSE
# ---------------------------------------------------------------------------


def _run_sse(case: Case, base_url: str) -> tuple[str, list[str], list[str], list[str], float]:
    import httpx

    url = f"{base_url.rstrip('/')}/teams/scout/runs"
    form = {"message": case.prompt, "stream": "true"}
    timeout_s = case.max_duration_s + 30

    content_deltas: list[str] = []
    final_content = ""
    tools: list[str] = []
    delegated: list[str] = []
    errors: list[str] = []

    start = time.monotonic()
    with httpx.Client(timeout=timeout_s) as client:
        with client.stream("POST", url, data=form) as response:
            response.raise_for_status()
            event_name: str | None = None
            for line in response.iter_lines():
                if not line:
                    event_name = None
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event_name == "TeamRunContent":
                    c = data.get("content")
                    if isinstance(c, str):
                        content_deltas.append(c)
                elif event_name == "TeamRunCompleted":
                    c = data.get("content")
                    if isinstance(c, str) and c:
                        final_content = c
                    for m in data.get("member_responses") or []:
                        if not isinstance(m, dict):
                            continue
                        aid = m.get("agent_id")
                        if aid:
                            delegated.append(str(aid))
                elif event_name in ("TeamToolCallCompleted", "ToolCallCompleted"):
                    t = data.get("tool") or {}
                    n = t.get("tool_name") or t.get("name")
                    if n:
                        tools.append(str(n))
                    err = t.get("error")
                    if err:
                        errors.append(str(err))
                elif event_name in ("TeamToolCallError", "TeamRunError", "ToolCallError", "RunError"):
                    msg = data.get("content") or data.get("error") or "(no message)"
                    errors.append(f"{event_name}: {msg}")
    duration = time.monotonic() - start

    if not final_content:
        final_content = "".join(content_deltas)
    return final_content, tools, delegated, errors, duration


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------


def _assert_case(
    case: Case,
    content: str,
    tools: list[str],
    delegated: list[str],
    errors: list[str],
    duration_s: float,
) -> list[str]:
    """Return a list of human-readable failure reasons. Empty = PASS."""
    fails: list[str] = []
    lower = content.lower()

    if case.expected_agent is None:
        if delegated:
            fails.append(f"leader should answer directly but delegated to: {delegated}")
    elif case.expected_agent not in delegated:
        fails.append(f"expected_agent={case.expected_agent!r} not in {delegated or 'no delegations'}")

    for needle in case.response_contains:
        if needle.lower() not in lower:
            fails.append(f"response missing substring: {needle!r}")
    for needle in case.response_forbids:
        if needle.lower() in lower:
            fails.append(f"response contains forbidden substring: {needle!r}")
    for pattern in case.response_matches:
        if not re.search(pattern, content, re.IGNORECASE):
            fails.append(f"response doesn't match regex: {pattern!r}")

    for want in case.expected_tools:
        if not any(want in t for t in tools):
            fails.append(f"expected tool {want!r} not called; saw {tools}")
    for bad in case.forbidden_tools:
        matches = [t for t in tools if bad in t]
        if matches:
            fails.append(f"forbidden tool {bad!r} was called: {matches}")

    if errors:
        for e in errors:
            fails.append(f"run error: {e}")

    if duration_s > case.max_duration_s:
        fails.append(f"duration {duration_s:.1f}s > max {case.max_duration_s}s")

    return fails


# ---------------------------------------------------------------------------
# Top-level — run one case
# ---------------------------------------------------------------------------


def run_case(case: Case, *, live: bool = False, base_url: str = "http://localhost:8000") -> CaseResult:
    """Execute one case. Install/restore the fixture around it."""
    transport = "live" if live else "in-process"

    prev: list[Any] | None = None
    if not live:
        try:
            prev = install_fixture(build_fixture(case.fixture))
        except Exception as exc:
            return CaseResult(
                case_id=case.id,
                status="ERROR",
                duration_s=0.0,
                transport=transport,
                failures=[f"fixture build/install failed: {type(exc).__name__}: {exc}"],
            )

    try:
        try:
            if live:
                content, tools, delegated, errors, duration = _run_sse(case, base_url)
            else:
                content, tools, delegated, errors, duration = _run_in_process(case)
        except Exception as exc:
            return CaseResult(
                case_id=case.id,
                status="ERROR",
                duration_s=0.0,
                transport=transport,
                failures=[f"{type(exc).__name__}: {exc}"],
            )

        failures = _assert_case(case, content, tools, delegated, errors, duration)
        return CaseResult(
            case_id=case.id,
            status="PASS" if not failures else "FAIL",
            duration_s=duration,
            transport=transport,
            failures=failures,
            response=content,
            tool_names=tools,
            delegated=delegated,
            errors=errors,
        )
    finally:
        if prev is not None:
            restore_contexts(prev)


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------


def write_diagnostic(case: Case, result: CaseResult) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{case.id}.md"
    path.write_text(_build_diagnostic(case, result))
    return path


def _build_diagnostic(case: Case, result: CaseResult) -> str:
    try:
        target = case.target_file.read_text()
    except OSError as exc:
        target = f"(could not read {case.target_file}: {exc})"

    parts: list[str] = [
        f"# Eval failure: {case.id}",
        "",
        f"**Status** {result.status} — duration {result.duration_s:.1f}s (budget {case.max_duration_s}s) — transport: {result.transport}",
        "",
        "## Case",
        f"- prompt: `{case.prompt[:400]}{'…' if len(case.prompt) > 400 else ''}`",
        f"- expected_agent: `{case.expected_agent}`",
        f"- response_contains: `{list(case.response_contains)}`",
        f"- response_forbids: `{list(case.response_forbids)}`",
        f"- response_matches: `{list(case.response_matches)}`",
        f"- expected_tools: `{list(case.expected_tools)}`",
        f"- forbidden_tools: `{list(case.forbidden_tools)}`",
        f"- fixture: `{case.fixture}`",
        f"- target_file: `{case.target_file.relative_to(REPO_ROOT)}`",
        "",
        "## Failures",
    ]
    parts.extend(f"- {f}" for f in (result.failures or ["(none)"]))
    parts.extend(
        [
            "",
            "## What happened",
            f"- delegated: `{result.delegated}`",
            f"- tools: `{result.tool_names}`",
            f"- errors: `{result.errors}`",
            "",
            "### Final content",
            "```",
            result.response or "(empty)",
            "```",
            "",
        ]
    )
    if result.transport == "live":
        parts.extend(
            [
                "## Docker logs (last 200 lines)",
                "```",
                _capture_logs(),
                "```",
                "",
            ]
        )
    parts.extend(
        [
            f"## Current target file: `{case.target_file.relative_to(REPO_ROOT)}`",
            "```python",
            target,
            "```",
            "",
            "## Instruction",
            f"Diagnose why this failed. Edit only `{case.target_file.relative_to(REPO_ROOT)}`. Do not run commands — the harness re-runs the case.",
        ]
    )
    return "\n".join(parts)


def _capture_logs() -> str:
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


__all__ = ["CaseResult", "RESULTS_DIR", "run_case", "write_diagnostic"]
