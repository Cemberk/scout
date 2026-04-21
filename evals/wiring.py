"""Wiring invariants — structural checks about agent + context composition.

No LLM, no network, no ``team.run()``. Each check binds to the shape
the architecture commits to; regressions fail loudly.

W1  Explorer's bound tools are read-only.
W2  Engineer has write-shape tools, no outbound sends.
W3  Doctor's bound tools are read-shaped, no writers.
W4  Leader's send tools align with ``SCOUT_ALLOW_SENDS`` + token env.
W5  Every registered ``ContextProvider`` has the expected shape.
W6  ``WikiContextProvider`` has the 5-method ingest/compile shape.
W7  ``LocalWikiBackend`` rejects ``../`` path escapes for both read and write.

Each check is a function that returns ``None`` on PASS and raises
``AssertionError`` with a diagnostic string on FAIL. The runner
collects exceptions and reports.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool_names(tools: Iterable[Any] | None) -> list[str]:
    """Best-effort extraction of tool names from an agent's ``tools=`` list.

    agno wraps decorated functions, ``Toolkit`` bundles, and ``Agent``
    instances. We duck-type across the known shapes and degrade quietly
    rather than raise.
    """
    names: list[str] = []
    if tools is None:
        return names
    # Callers sometimes pass the attribute directly — which agno types as
    # ``list | Callable[..., list]``. If it's a callable factory, invoke it.
    if callable(tools) and not hasattr(tools, "__iter__"):
        try:
            tools = tools()
        except Exception:
            return names
    for item in tools:
        # agno @tool returns a Function instance with a .name attribute.
        name = getattr(item, "name", None)
        if isinstance(name, str) and name:
            names.append(name)
            continue

        # Toolkit with a .functions dict of name -> fn
        fns = getattr(item, "functions", None)
        if isinstance(fns, dict):
            names.extend(str(k) for k in fns.keys())
            continue

        # Toolkit with a .tools list
        sub = getattr(item, "tools", None)
        if isinstance(sub, (list, tuple)):
            for t in sub:
                n = getattr(t, "name", None)
                if isinstance(n, str) and n:
                    names.append(n)
            continue

        # Fall back to the underlying callable's __name__ (tool-decorated
        # callables expose it even when they don't carry .name).
        entry = getattr(item, "entrypoint", None)
        if callable(entry):
            fn_name = getattr(entry, "__name__", None)
            if isinstance(fn_name, str) and fn_name:
                names.append(fn_name)
                continue

        # Last resort: class name — so we can still spot Toolkits we
        # couldn't decompose.
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
    """Explorer's tool list must be read-only.

    ``set_runtime(wiki, contexts)`` installs the registry and rewires
    Explorer in one call. Run the check with a real wiki so the
    steady-state tool shape matches production.
    """
    from scout.agents.explorer import explorer
    from scout.context.config import build_wiki
    from scout.tools.ask_context import get_contexts, get_wiki, set_runtime

    prev_wiki = get_wiki()
    prev_contexts = get_contexts()
    try:
        set_runtime(build_wiki(), [])
        names = _tool_names(explorer.tools or [])  # type: ignore[arg-type]
    finally:
        set_runtime(prev_wiki, prev_contexts)

    forbidden_substrings = (
        "ingest_url",
        "ingest_text",
        "trigger_compile",
        "send_email",
        "send_email_reply",
        "send_message",
        "create_event",
        "update_event",
        "delete_event",
        "post_message",
    )
    leaks = [n for n in names for bad in forbidden_substrings if bad in n]
    if leaks:
        raise AssertionError(f"Explorer has forbidden tool(s): {leaks}. Full tool list: {names}")

    expected_substrings = ("query_wiki", "list_contexts", "update_learnings")
    missing = [want for want in expected_substrings if not any(want in n for n in names)]
    if missing:
        raise AssertionError(f"Explorer missing expected tool(s) {missing}. Full tool list: {names}")


# ---------------------------------------------------------------------------
# W2 — Engineer write-shape
# ---------------------------------------------------------------------------


def w2_engineer_write_shape() -> None:
    """Engineer's wiki tools come from ``wiki.get_tools(include_writes=True)``.

    ``set_runtime`` wires them in. Run with a real wiki so the tool
    shape matches production.
    """
    from scout.agents.engineer import engineer
    from scout.context.config import build_wiki
    from scout.tools.ask_context import get_contexts, get_wiki, set_runtime

    prev_wiki = get_wiki()
    prev_contexts = get_contexts()
    try:
        set_runtime(build_wiki(), [])
        names = _tool_names(engineer.tools or [])  # type: ignore[arg-type]
    finally:
        set_runtime(prev_wiki, prev_contexts)

    expected = ("ingest_url", "ingest_text", "trigger_compile", "introspect_schema", "update_learnings")
    missing = [want for want in expected if not any(want in n for n in names)]
    if missing:
        raise AssertionError(f"Engineer missing expected tool(s) {missing}. Full tool list: {names}")

    forbidden = ("send_email", "send_email_reply", "create_event", "post_message", "delete_event", "update_event")
    leaks = [n for n in names for bad in forbidden if bad in n]
    if leaks:
        raise AssertionError(f"Engineer has send tool(s) it shouldn't: {leaks}. Full tool list: {names}")


# ---------------------------------------------------------------------------
# W3 — Doctor readonly
# ---------------------------------------------------------------------------


def w3_doctor_readonly() -> None:
    from scout.agents.doctor import doctor

    names = _tool_names(doctor.tools or [])  # type: ignore[arg-type]
    expected = ("health", "health_all", "db_health", "env_report", "update_learnings")
    missing = [want for want in expected if not any(want in n for n in names)]
    if missing:
        raise AssertionError(f"Doctor missing expected tool(s) {missing}. Full tool list: {names}")

    forbidden = (
        "ingest_url",
        "ingest_text",
        "trigger_compile",
        "send_email",
        "send_email_reply",
        "create_event",
        "delete_event",
        "post_message",
    )
    leaks = [n for n in names for bad in forbidden if bad in n]
    if leaks:
        raise AssertionError(f"Doctor has writer/send tool(s) it shouldn't: {leaks}. Full tool list: {names}")


# ---------------------------------------------------------------------------
# W4 — Leader send gating matches current env
# ---------------------------------------------------------------------------


def w4_leader_send_gating() -> None:
    from scout import team as team_module

    names = _tool_names(team_module.leader_tools or [])

    allow_sends = os.getenv("SCOUT_ALLOW_SENDS", "").lower() in ("true", "1", "yes")
    slack_set = bool(os.getenv("SLACK_BOT_TOKEN", ""))
    google_set = bool(
        os.getenv("GOOGLE_CLIENT_ID", "")
        and os.getenv("GOOGLE_CLIENT_SECRET", "")
        and os.getenv("GOOGLE_PROJECT_ID", "")
    )

    # Slack: SlackTools is always wired with send_message enabled when
    # SLACK_BOT_TOKEN is set (independent of SCOUT_ALLOW_SENDS, per spec §4.5).
    if slack_set:
        if not any("send_message" in n for n in names):
            raise AssertionError(f"SLACK_BOT_TOKEN set but no send_message tool on Leader. Tools: {names}")
    else:
        if any("send_message" in n for n in names):
            raise AssertionError(f"SLACK_BOT_TOKEN unset but send_message tool is wired. Tools: {names}")

    # Gmail + Calendar: tools are present when GOOGLE_* is set, but send
    # functions are excluded unless SCOUT_ALLOW_SENDS=true.
    if google_set and allow_sends:
        # Send tools should be present.
        if not any("send_email" in n for n in names):
            raise AssertionError(
                f"SCOUT_ALLOW_SENDS=true + Google configured, but send_email not wired. Tools: {names}"
            )
    else:
        # Send tools must NOT be present.
        leaks = [n for n in names if "send_email" in n or "create_event" in n or "delete_event" in n]
        if leaks:
            raise AssertionError(
                f"Send tools leaked without SCOUT_ALLOW_SENDS=true (+ Google env): {leaks}. Tools: {names}"
            )


# ---------------------------------------------------------------------------
# W5 — ContextProvider shape
# ---------------------------------------------------------------------------


def w5_context_protocol_shape() -> None:
    from scout.context.base import ContextProvider
    from scout.context.config import build_contexts

    built = build_contexts()
    # Empty list is fine (SCOUT_CONTEXTS unset) — shape check is vacuous
    # but we still want the import path to work.
    for ctx in built:
        for attr in ("id", "name", "kind"):
            if not isinstance(getattr(ctx, attr, None), str):
                raise AssertionError(f"ContextProvider {type(ctx).__name__!s} missing/non-string attr {attr!r}")
        for method in ("health", "query"):
            if not callable(getattr(ctx, method, None)):
                raise AssertionError(f"ContextProvider {ctx.id!r} missing callable method {method!r}")
        if not isinstance(ctx, ContextProvider):
            raise AssertionError(f"ContextProvider {ctx.id!r} is not a subclass of ContextProvider")


# ---------------------------------------------------------------------------
# W6 — WikiContextProvider five-method shape
# ---------------------------------------------------------------------------


def w6_wiki_context_shape() -> None:
    from scout.context.wiki.provider import WikiContextProvider

    for attr in ("id", "name", "kind"):
        if not isinstance(getattr(WikiContextProvider, attr, None), str):
            raise AssertionError(f"WikiContextProvider missing/non-string class attr {attr!r}")
    for method in ("health", "query", "ingest_url", "ingest_text", "compile"):
        if not callable(getattr(WikiContextProvider, method, None)):
            raise AssertionError(f"WikiContextProvider missing callable method {method!r}")


# ---------------------------------------------------------------------------
# W7 — LocalWikiBackend path-escape guard
# ---------------------------------------------------------------------------


def w7_local_backend_path_escape() -> None:
    from scout.context.wiki.backends.local import LocalWikiBackend

    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalWikiBackend(tmp)
        try:
            backend.read_bytes("../escape.txt")
        except ValueError:
            pass
        except Exception as exc:
            raise AssertionError(
                f"LocalWikiBackend.read_bytes('../escape.txt') raised {type(exc).__name__} (want ValueError): {exc}"
            ) from exc
        else:
            raise AssertionError("LocalWikiBackend.read_bytes accepted '../escape.txt' — path escape guard broken")

        try:
            backend.write_bytes("../escape.txt", b"oops")
        except ValueError:
            pass
        except Exception as exc:
            raise AssertionError(
                f"LocalWikiBackend.write_bytes('../escape.txt') raised {type(exc).__name__} (want ValueError): {exc}"
            ) from exc
        else:
            # Clean up the file that escaped, so the next run starts clean.
            escaped = Path(tmp).parent / "escape.txt"
            if escaped.exists():
                escaped.unlink()
            raise AssertionError("LocalWikiBackend.write_bytes accepted '../escape.txt' — path escape guard broken")


# ---------------------------------------------------------------------------
# Registry + run helper
# ---------------------------------------------------------------------------


INVARIANTS: tuple[tuple[str, str, Callable[[], None]], ...] = (
    ("W1", "explorer_readonly", w1_explorer_readonly),
    ("W2", "engineer_write_shape", w2_engineer_write_shape),
    ("W3", "doctor_readonly", w3_doctor_readonly),
    ("W4", "leader_send_gating", w4_leader_send_gating),
    ("W5", "context_protocol_shape", w5_context_protocol_shape),
    ("W6", "wiki_context_shape", w6_wiki_context_shape),
    ("W7", "local_backend_path_escape", w7_local_backend_path_escape),
)


def run_all(verbose: bool = False) -> list[InvariantResult]:
    """Run every invariant. Returns a result per check."""
    results: list[InvariantResult] = []
    for id_, name, fn in INVARIANTS:
        try:
            fn()
            results.append(InvariantResult(id=id_, name=name, passed=True))
        except Exception as exc:  # AssertionError + anything odd from imports
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
