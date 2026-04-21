"""Run behavioral eval cases.

One case, two transports: in-process ``team.run()`` by default, or
``POST /teams/scout/runs`` SSE when ``live=True``. Assertion model is
identical — transport only changes how content + tools + delegations
are captured.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal

from evals.cases import Case

Status = Literal["PASS", "FAIL", "SKIPPED", "ERROR"]


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


def build_fixture(name: str) -> Fixture:
    """Build a fixture by name: ``default`` | ``none`` | ``real``."""
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
        # Env-built contexts — hits live providers. Needs API keys.
        from scout.contexts import build_contexts

        return Fixture(contexts=build_contexts())

    raise ValueError(f"unknown fixture {name!r}")


def install_fixture(fixture: Fixture) -> list[Any]:
    """Install the fixture; return the prior contexts so the caller can restore."""
    from scout.contexts import get_contexts, publish_contexts

    prev = get_contexts()
    publish_contexts(fixture.contexts)
    return prev


def restore_contexts(prev: list[Any]) -> None:
    from scout.contexts import publish_contexts

    publish_contexts(prev)


def _stub_context(ctx_id: str, display_name: str, answer_text: str):
    """A ContextProvider subclass with a canned ``query()`` answer."""
    from scout.context.provider import Answer, ContextProvider
    from scout.context.provider import Status as ProviderStatus

    class StubContext(ContextProvider):
        def __init__(self) -> None:
            super().__init__(id=ctx_id, name=display_name)

        def status(self):
            return ProviderStatus(ok=True, detail=f"stub {ctx_id}")

        async def astatus(self):
            return self.status()

        def query(self, question, *, limit=10):
            return Answer(text=answer_text)

        async def aquery(self, question, *, limit=10):
            return Answer(text=answer_text)

    return StubContext()


# ---------------------------------------------------------------------------
# Transport — in-process
# ---------------------------------------------------------------------------


def _run_in_process(case: Case) -> tuple[str, list[str], list[str], list[str], float]:
    from scout.team import scout as team

    start = time.monotonic()
    result = team.run(case.prompt)
    duration = time.monotonic() - start

    content = getattr(result, "content", None) or ""
    tools = _tool_names_from(result)
    errors = _tool_errors_from(result)
    delegated: list[str] = []

    for member in getattr(result, "member_responses", None) or []:
        aid = getattr(member, "agent_id", None)
        if aid is None and isinstance(member, dict):
            aid = member.get("agent_id")
        if aid:
            delegated.append(str(aid))
        tools.extend(_tool_names_from(member))
        errors.extend(_tool_errors_from(member))

    return content, tools, delegated, errors, duration


def _tool_names_from(obj: Any) -> list[str]:
    """Tool names from a run result or member response."""
    names: list[str] = []
    for t in _iter_tools(obj):
        if isinstance(t, dict):
            name = t.get("tool_name") or t.get("name")
        else:
            name = (
                getattr(t, "tool_name", None)
                or getattr(t, "name", None)
                or getattr(getattr(t, "function", None), "name", None)
            )
        if name:
            names.append(str(name))
    return names


def _tool_errors_from(obj: Any) -> list[str]:
    errors: list[str] = []
    for t in _iter_tools(obj):
        err = t.get("error") if isinstance(t, dict) else getattr(t, "error", None)
        if err:
            errors.append(str(err))
    return errors


def _iter_tools(obj: Any) -> list[Any]:
    t_list = getattr(obj, "tools", None)
    return list(t_list) if isinstance(t_list, (list, tuple)) else []


# ---------------------------------------------------------------------------
# Transport — live SSE
# ---------------------------------------------------------------------------


def _run_sse(case: Case, base_url: str) -> tuple[str, list[str], list[str], list[str], float]:
    """POST the prompt, parse the SSE stream, collect content + tools + delegations."""
    import httpx

    url = f"{base_url.rstrip('/')}/teams/scout/runs"
    form = {"message": case.prompt, "stream": "true"}
    timeout_s = case.max_duration_s + 30

    deltas: list[str] = []
    final_content = ""
    tools: list[str] = []
    delegated: list[str] = []
    errors: list[str] = []

    start = time.monotonic()
    with httpx.Client(timeout=timeout_s) as client, client.stream("POST", url, data=form) as response:
        response.raise_for_status()
        for event_name, data in _sse_events(response):
            if event_name == "TeamRunContent":
                c = data.get("content")
                if isinstance(c, str):
                    deltas.append(c)

            elif event_name == "TeamRunCompleted":
                c = data.get("content")
                if isinstance(c, str) and c:
                    final_content = c
                for m in data.get("member_responses") or []:
                    if isinstance(m, dict) and m.get("agent_id"):
                        delegated.append(str(m["agent_id"]))

            elif event_name in ("TeamToolCallCompleted", "ToolCallCompleted"):
                t = data.get("tool") or {}
                name = t.get("tool_name") or t.get("name")
                if name:
                    tools.append(str(name))
                if err := t.get("error"):
                    errors.append(str(err))

            elif event_name in ("TeamToolCallError", "TeamRunError", "ToolCallError", "RunError"):
                msg = data.get("content") or data.get("error") or "(no message)"
                errors.append(f"{event_name}: {msg}")

    duration = time.monotonic() - start
    content = final_content or "".join(deltas)
    return content, tools, delegated, errors, duration


def _sse_events(response: Any) -> Iterator[tuple[str | None, dict[str, Any]]]:
    """Yield ``(event_name, data)`` from an SSE stream."""
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
            yield event_name, json.loads(raw)
        except json.JSONDecodeError:
            continue


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
    """Return human-readable failure reasons. Empty list = PASS."""
    fails: list[str] = []
    lower = content.lower()

    # Who answered
    if case.expected_agent is None and delegated:
        fails.append(f"leader should answer directly but delegated to: {delegated}")
    elif case.expected_agent and case.expected_agent not in delegated:
        fails.append(f"expected_agent={case.expected_agent!r} not in {delegated or 'no delegations'}")

    # Response content
    for needle in case.response_contains:
        if needle.lower() not in lower:
            fails.append(f"response missing substring: {needle!r}")
    for needle in case.response_forbids:
        if needle.lower() in lower:
            fails.append(f"response contains forbidden substring: {needle!r}")
    for pattern in case.response_matches:
        if not re.search(pattern, content, re.IGNORECASE):
            fails.append(f"response doesn't match regex: {pattern!r}")

    # Tools called
    for want in case.expected_tools:
        if not any(want in t for t in tools):
            fails.append(f"expected tool {want!r} not called; saw {tools}")
    for bad in case.forbidden_tools:
        if hits := [t for t in tools if bad in t]:
            fails.append(f"forbidden tool {bad!r} was called: {hits}")

    # Errors and timing
    fails.extend(f"run error: {e}" for e in errors)
    if duration_s > case.max_duration_s:
        fails.append(f"duration {duration_s:.1f}s > max {case.max_duration_s}s")

    return fails


# ---------------------------------------------------------------------------
# Run one case
# ---------------------------------------------------------------------------


def run_case(case: Case, *, live: bool = False, base_url: str = "http://localhost:8000") -> CaseResult:
    """Run one case and return the result.

    In-process mode installs the named fixture first and restores the prior
    registry at the end. Live mode uses whatever the container already has.
    """
    transport = "live" if live else "in-process"

    prev: list[Any] | None = None
    if not live:
        try:
            prev = install_fixture(build_fixture(case.fixture))
        except Exception as exc:
            return _error(case.id, transport, f"fixture failed: {type(exc).__name__}: {exc}")

    try:
        try:
            if live:
                content, tools, delegated, errors, duration = _run_sse(case, base_url)
            else:
                content, tools, delegated, errors, duration = _run_in_process(case)
        except Exception as exc:
            return _error(case.id, transport, f"{type(exc).__name__}: {exc}")

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


def _error(case_id: str, transport: str, msg: str) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        status="ERROR",
        duration_s=0.0,
        transport=transport,
        failures=[msg],
    )
