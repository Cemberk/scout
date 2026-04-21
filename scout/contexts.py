"""
Context Registry
================

Env-driven wiring + runtime registry for the contexts Scout's agents use.
``build_contexts()`` assembles the context list from env once at startup.
``set_runtime(contexts)`` publishes that list globally and rewires
Explorer's per-provider tools in one call.
"""

from __future__ import annotations

import json
import logging
from os import getenv

from agno.tools import tool

from scout.context.provider import ContextProvider
from scout.context.web.backends.exa_mcp import ExaMCPBackend
from scout.context.web.backends.parallel import ParallelBackend
from scout.context.web.provider import WebContextProvider

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Env-driven factory
# ---------------------------------------------------------------------------


def build_contexts() -> list[ContextProvider]:
    """Build the registered contexts from env."""
    contexts: list[ContextProvider] = []
    web = _build_web()
    if web is not None:
        contexts.append(web)
        log.info("context: web (%s)", web.backend.kind)
    return contexts


def _build_web() -> WebContextProvider | None:
    try:
        if getenv("PARALLEL_API_KEY"):
            return WebContextProvider(backend=ParallelBackend())
        return WebContextProvider(backend=ExaMCPBackend())
    except Exception:
        log.exception("context: web build failed; skipping")
        return None


# ---------------------------------------------------------------------------
# Runtime registry
# ---------------------------------------------------------------------------


_contexts: list[ContextProvider] = []


def set_runtime(contexts: list[ContextProvider]) -> None:
    """Install the registry singleton and rewire Explorer's tool list."""
    global _contexts
    _contexts = list(contexts)

    # Deferred: Explorer imports from this module, so avoid circularity.
    from scout.agents.explorer import explorer, explorer_tools

    explorer.tools = explorer_tools()  # type: ignore[assignment]


def get_contexts() -> list[ContextProvider]:
    return list(_contexts)


@tool
def list_contexts() -> str:
    """List registered contexts with current status.

    Returns:
        JSON list of ``{id, name, ok, detail}``.
    """
    rows = []
    for ctx in _contexts:
        try:
            s = ctx.status()
            ok = s.ok
            detail = s.detail
        except Exception as exc:
            ok = False
            detail = f"{type(exc).__name__}: {exc}"
        rows.append({"id": ctx.id, "name": ctx.name, "ok": ok, "detail": detail})
    return json.dumps(rows)
