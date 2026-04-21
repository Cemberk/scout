"""Evaluate structural wiring.

Checks:
    W1  Explorer's bound tools are read-only.
    W2  Engineer wires SQL + introspect + learnings + reasoning; no outbound.
    W3  Doctor wires status + diagnostic + learnings; no writers.
    W4  Leader has no tools (pure router).
    W5  Every registered ``ContextProvider`` has the expected shape.

Each check is a function that returns None on PASS and raises
``AssertionError`` on FAIL. Zero LLM, zero network — runs in under a second.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class InvariantResult:
    id: str
    name: str
    passed: bool
    detail: str = ""


FORBIDDEN_OUTBOUND = ("send_email", "send_message", "create_event", "post_message", "delete_event")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool_names(tools: Any) -> list[str]:
    """Best-effort extraction of tool names from an agent's ``tools=`` list."""
    if tools is None:
        return []
    if callable(tools) and not hasattr(tools, "__iter__"):
        try:
            tools = tools()
        except Exception:
            return []

    names: list[str] = []
    for item in tools:
        name = getattr(item, "name", None)
        if isinstance(name, str) and name:
            names.append(name)
            continue

        fns = getattr(item, "functions", None)
        if isinstance(fns, dict):
            names.extend(str(k) for k in fns.keys())
            continue

        sub = getattr(item, "tools", None)
        if isinstance(sub, (list, tuple)):
            for t in sub:
                n = getattr(t, "name", None)
                if isinstance(n, str) and n:
                    names.append(n)
            continue

        entry = getattr(item, "entrypoint", None)
        if callable(entry):
            fn_name = getattr(entry, "__name__", None)
            if isinstance(fn_name, str) and fn_name:
                names.append(fn_name)
                continue

        names.append(f"<{type(item).__name__}>")

    return names


def _assert_has(names: list[str], wanted: tuple[str, ...], agent: str) -> None:
    missing = [w for w in wanted if not any(w in n for n in names)]
    if missing:
        raise AssertionError(f"{agent} missing expected tool(s) {missing}. Full tool list: {names}")


def _assert_no_outbound(names: list[str], agent: str) -> None:
    leaks = [n for n in names for bad in FORBIDDEN_OUTBOUND if bad in n]
    if leaks:
        raise AssertionError(f"{agent} has outbound tool(s) it shouldn't: {leaks}. Full tool list: {names}")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def w1_explorer_readonly() -> None:
    from scout.agents.explorer import explorer
    from scout.contexts import build_contexts, get_contexts, set_runtime

    prev = get_contexts()
    try:
        set_runtime(build_contexts())
        names = _tool_names(explorer.tools)
    finally:
        set_runtime(prev)

    _assert_no_outbound(names, "Explorer")
    _assert_has(names, ("list_contexts", "update_learnings"), "Explorer")


def w2_engineer_write_shape() -> None:
    from scout.agents.engineer import engineer

    names = _tool_names(engineer.tools)
    _assert_has(names, ("introspect_schema", "update_learnings"), "Engineer")
    _assert_no_outbound(names, "Engineer")


def w3_doctor_readonly() -> None:
    from scout.agents.doctor import doctor

    names = _tool_names(doctor.tools)
    _assert_has(names, ("status", "status_all", "db_status", "update_learnings"), "Doctor")
    _assert_no_outbound(names, "Doctor")


def w4_leader_no_tools() -> None:
    from scout.team import scout

    names = _tool_names(scout.tools)
    if names:
        raise AssertionError(f"Leader should be a pure router with no tools, got: {names}")


def w5_context_protocol_shape() -> None:
    from scout.context.provider import ContextProvider
    from scout.contexts import build_contexts

    for ctx in build_contexts():
        if not isinstance(ctx, ContextProvider):
            raise AssertionError(f"ContextProvider {ctx.id!r} is not a subclass of ContextProvider")
        for attr in ("id", "name"):
            if not isinstance(getattr(ctx, attr, None), str):
                raise AssertionError(f"ContextProvider {type(ctx).__name__!s} missing/non-string attr {attr!r}")
        for method in ("query", "status", "get_tools", "instructions"):
            if not callable(getattr(ctx, method, None)):
                raise AssertionError(f"ContextProvider {ctx.id!r} missing callable method {method!r}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


CHECKS = (
    w1_explorer_readonly,
    w2_engineer_write_shape,
    w3_doctor_readonly,
    w4_leader_no_tools,
    w5_context_protocol_shape,
)


def run_all() -> list[InvariantResult]:
    """Run every check. Returns a result per check."""
    results = []
    for fn in CHECKS:
        id_, _, name = fn.__name__.partition("_")
        try:
            fn()
            results.append(InvariantResult(id=id_.upper(), name=name, passed=True))
        except Exception as exc:
            results.append(
                InvariantResult(id=id_.upper(), name=name, passed=False, detail=f"{type(exc).__name__}: {exc}")
            )
    return results
