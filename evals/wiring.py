"""Evaluate structural wiring.

Checks:
    W1  Scout has every provider's tools + `list_contexts`; no bare `SQLTools`.
    W2  `DatabaseContextProvider` exposes `query_crm` AND `update_crm`.
    W3  Schema guard rejects DDL/DML targeting `public`/`ai` on the scout engine.
    W4  Every registered `ContextProvider` has the expected shape.
    W5  GDrive provider uses `ScoutGoogleDriveTools`, not bare `GoogleDriveTools`.

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


def w1_scout_tool_surface() -> None:
    """Scout exposes every provider's tools + `list_contexts`, nothing outbound.

    With single-agent Scout all tools are resolved through the registry.
    The factory is a callable so this check resolves it to a concrete list.
    """
    from scout.contexts import build_contexts, get_contexts, update_contexts
    from scout.team import scout

    prev = get_contexts()
    try:
        build_contexts()
        names = _tool_names(scout.tools)
    finally:
        update_contexts(prev)

    _assert_no_outbound(names, "Scout")
    _assert_has(names, ("list_contexts", "query_crm", "update_crm"), "Scout")

    # Scout should not hold bare SQLTools — SQL lives inside the CRM
    # provider's sub-agents. If this regresses we lose the read/write
    # separation the CRM provider enforces.
    if any("run_sql_query" in n or "sql_tools" in n.lower() for n in names):
        raise AssertionError(
            f"Scout has bare SQL tools; SQL must be wrapped by the CRM provider. Tool list: {names}"
        )


def w2_crm_provider_surface() -> None:
    """`DatabaseContextProvider` exposes both `query_crm` and `update_crm`."""
    from scout.context.database import DatabaseContextProvider

    provider = DatabaseContextProvider()
    tools = provider.get_tools()
    names = _tool_names(tools)
    _assert_has(names, ("query_crm", "update_crm"), "DatabaseContextProvider")

    # The base `aupdate()` raises NotImplementedError; the CRM provider
    # must override both `aquery` and `aupdate` — otherwise `update_crm`
    # returns a read-only error.
    base_aupdate = type(provider).__mro__[1].aupdate  # type: ignore[attr-defined]
    crm_aupdate = type(provider).aupdate
    if crm_aupdate is base_aupdate:
        raise AssertionError("DatabaseContextProvider.aupdate is not overridden — update_crm will always return read-only")


def w3_schema_guard_blocks_non_scout_writes() -> None:
    """The scout engine rejects DDL/DML against `public` / `ai` at the hook.

    Belt-and-suspenders on top of `search_path=scout,public`. Exercises the
    guard directly; if a future refactor removes the before-cursor hook,
    this check flips red immediately.
    """
    from sqlalchemy import text

    from db import get_sql_engine

    engine = get_sql_engine()
    bad_statements = [
        "CREATE TABLE public.pwned (id int)",
        "INSERT INTO public.foo VALUES (1)",
        "INSERT INTO ai.secrets VALUES (1)",
        "DELETE FROM public.users",
        "UPDATE ai.sessions SET deleted = true",
    ]
    for stmt in bad_statements:
        try:
            with engine.connect() as conn:
                conn.execute(text(stmt))
        except RuntimeError as exc:
            if "public" not in str(exc) and "ai" not in str(exc) and "scout" not in str(exc):
                raise AssertionError(
                    f"Unexpected error text for {stmt!r}: {exc}"
                ) from exc
            continue
        except Exception as exc:
            # Anything else (e.g. OperationalError because table missing) is
            # NOT acceptable — the guard should fire first.
            raise AssertionError(
                f"Guard didn't fire for {stmt!r}; got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(f"Guard let through: {stmt!r}")


def w4_context_protocol_shape() -> None:
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


def w5_gdrive_uses_scout_subclass() -> None:
    """GDrive provider must use `ScoutGoogleDriveTools`, not bare `GoogleDriveTools`.

    The bare upstream toolkit queries `corpora=user` and misses every file
    the SA doesn't own directly (shared folders, Shared Drives). Regressing
    to bare `GoogleDriveTools` silently breaks every real deployment, so
    pin the subclass here.
    """
    from scout.context.gdrive import GDriveContextProvider
    from scout.context.gdrive.tools import ScoutGoogleDriveTools

    provider = GDriveContextProvider(service_account_path="/tmp/eval-wiring-stub.json")
    toolkit = provider._ensure_tools()
    if not isinstance(toolkit, ScoutGoogleDriveTools):
        raise AssertionError(
            f"GDriveContextProvider._ensure_tools() returned {type(toolkit).__name__}; "
            f"expected ScoutGoogleDriveTools so shared-folder / Shared-Drive files are visible"
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


CHECKS = (
    w1_scout_tool_surface,
    w2_crm_provider_surface,
    w3_schema_guard_blocks_non_scout_writes,
    w4_context_protocol_shape,
    w5_gdrive_uses_scout_subclass,
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
