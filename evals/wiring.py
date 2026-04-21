"""Wiring invariants — structural checks about agent + context composition.

No LLM, no network, no ``team.run()``. Each check binds to the shape
the architecture commits to; regressions fail loudly.

W1  Explorer's bound tools are read-only.
W2  Engineer's tools are SQL + introspect + learnings + reasoning; no outbound.
W3  Doctor's tools are status + diagnostic + learnings; no writers.
W4  Leader has no tools (pure router).
W5  Every registered ``ContextProvider`` has the expected shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


def _tool_names(tools: Iterable[Any] | None) -> list[str]:
    """Best-effort extraction of tool names from an agent's ``tools=`` list."""
    names: list[str] = []
    if tools is None:
        return names
    if callable(tools) and not hasattr(tools, "__iter__"):
        try:
            tools = tools()
        except Exception:
            return names
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
        cls = type(item).__name__
        if cls:
            names.append(f"<{cls}>")
    return names


@dataclass
class InvariantResult:
    """Result from one invariant check."""

    id: str
    name: str
    passed: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# W1 — Explorer readonly
# ---------------------------------------------------------------------------


def w1_explorer_readonly() -> None:
    """Explorer's tool list must be read-only and include expected helpers."""
    from scout.agents.explorer import explorer
    from scout.contexts import build_contexts, get_contexts, set_runtime

    prev_contexts = get_contexts()
    try:
        set_runtime(build_contexts())
        names = _tool_names(explorer.tools or [])  # type: ignore[arg-type]
    finally:
        set_runtime(prev_contexts)

    forbidden = ("send_email", "send_message", "create_event", "post_message", "delete_event")
    leaks = [n for n in names for bad in forbidden if bad in n]
    if leaks:
        raise AssertionError(f"Explorer has forbidden tool(s): {leaks}. Full tool list: {names}")

    expected = ("list_contexts", "update_learnings")
    missing = [want for want in expected if not any(want in n for n in names)]
    if missing:
        raise AssertionError(f"Explorer missing expected tool(s) {missing}. Full tool list: {names}")


# ---------------------------------------------------------------------------
# W2 — Engineer write-shape
# ---------------------------------------------------------------------------


def w2_engineer_write_shape() -> None:
    """Engineer has SQL + introspect + learnings + reasoning; no outbound."""
    from scout.agents.engineer import engineer

    names = _tool_names(engineer.tools or [])  # type: ignore[arg-type]
    expected = ("introspect_schema", "update_learnings")
    missing = [want for want in expected if not any(want in n for n in names)]
    if missing:
        raise AssertionError(f"Engineer missing expected tool(s) {missing}. Full tool list: {names}")

    forbidden = ("send_email", "send_message", "create_event", "post_message", "delete_event")
    leaks = [n for n in names for bad in forbidden if bad in n]
    if leaks:
        raise AssertionError(f"Engineer has outbound tool(s) it shouldn't: {leaks}. Full tool list: {names}")


# ---------------------------------------------------------------------------
# W3 — Doctor readonly
# ---------------------------------------------------------------------------


def w3_doctor_readonly() -> None:
    from scout.agents.doctor import doctor

    names = _tool_names(doctor.tools or [])  # type: ignore[arg-type]
    expected = ("status", "status_all", "db_status", "env_report", "update_learnings")
    missing = [want for want in expected if not any(want in n for n in names)]
    if missing:
        raise AssertionError(f"Doctor missing expected tool(s) {missing}. Full tool list: {names}")

    forbidden = ("send_email", "send_message", "create_event", "post_message", "delete_event")
    leaks = [n for n in names for bad in forbidden if bad in n]
    if leaks:
        raise AssertionError(f"Doctor has writer/send tool(s) it shouldn't: {leaks}. Full tool list: {names}")


# ---------------------------------------------------------------------------
# W4 — Leader has no tools (pure router)
# ---------------------------------------------------------------------------


def w4_leader_no_tools() -> None:
    from scout.team import scout

    names = _tool_names(scout.tools or [])  # type: ignore[arg-type]
    if names:
        raise AssertionError(f"Leader should be a pure router with no tools, got: {names}")


# ---------------------------------------------------------------------------
# W5 — ContextProvider shape
# ---------------------------------------------------------------------------


def w5_context_protocol_shape() -> None:
    from scout.context.provider import ContextProvider
    from scout.contexts import build_contexts

    built = build_contexts()
    for ctx in built:
        for attr in ("id", "name"):
            if not isinstance(getattr(ctx, attr, None), str):
                raise AssertionError(f"ContextProvider {type(ctx).__name__!s} missing/non-string attr {attr!r}")
        for method in ("query", "status", "get_tools", "instructions"):
            if not callable(getattr(ctx, method, None)):
                raise AssertionError(f"ContextProvider {ctx.id!r} missing callable method {method!r}")
        if not isinstance(ctx, ContextProvider):
            raise AssertionError(f"ContextProvider {ctx.id!r} is not a subclass of ContextProvider")


# ---------------------------------------------------------------------------
# Registry + run helper
# ---------------------------------------------------------------------------


INVARIANTS: tuple[tuple[str, str, Callable[[], None]], ...] = (
    ("W1", "explorer_readonly", w1_explorer_readonly),
    ("W2", "engineer_write_shape", w2_engineer_write_shape),
    ("W3", "doctor_readonly", w3_doctor_readonly),
    ("W4", "leader_no_tools", w4_leader_no_tools),
    ("W5", "context_protocol_shape", w5_context_protocol_shape),
)


def run_all(verbose: bool = False) -> list[InvariantResult]:
    """Run every invariant. Returns a result per check."""
    del verbose
    results: list[InvariantResult] = []
    for id_, name, fn in INVARIANTS:
        try:
            fn()
            results.append(InvariantResult(id=id_, name=name, passed=True))
        except Exception as exc:
            results.append(
                InvariantResult(
                    id=id_,
                    name=name,
                    passed=False,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


__all__ = ["INVARIANTS", "InvariantResult", "run_all"]
