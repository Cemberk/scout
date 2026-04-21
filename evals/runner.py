"""Run behavioral eval cases in-process.

Assertions on content + tools + delegations from ``team.run()``.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from evals.cases import Case

Status = Literal["PASS", "FAIL", "ERROR"]


@dataclass
class CaseResult:
    case_id: str
    status: Status
    duration_s: float
    failures: list[str] = field(default_factory=list)
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
    """Build a fixture by name: ``default`` | ``real``."""
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

        def query(self, question):
            return Answer(text=answer_text)

        async def aquery(self, question):
            return Answer(text=answer_text)

    return StubContext()


# ---------------------------------------------------------------------------
# Transport — in-process team.run()
# ---------------------------------------------------------------------------


def _run_in_process(case: Case) -> tuple[str, list[str], list[str], list[str], float]:
    from scout.team import scout as team

    start = time.monotonic()
    result = asyncio.run(team.arun(case.prompt))
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


def run_case(case: Case) -> CaseResult:
    """Run one case and return the result."""
    try:
        prev = install_fixture(build_fixture(case.fixture))
    except Exception as exc:
        return _error(case.id, f"fixture failed: {type(exc).__name__}: {exc}")

    try:
        try:
            content, tools, delegated, errors, duration = _run_in_process(case)
        except Exception as exc:
            return _error(case.id, f"{type(exc).__name__}: {exc}")

        failures = _assert_case(case, content, tools, delegated, errors, duration)
        return CaseResult(
            case_id=case.id,
            status="PASS" if not failures else "FAIL",
            duration_s=duration,
            failures=failures,
            response=content,
            tool_names=tools,
            delegated=delegated,
            errors=errors,
        )
    finally:
        restore_contexts(prev)


def _error(case_id: str, msg: str) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        status="ERROR",
        duration_s=0.0,
        failures=[msg],
    )
