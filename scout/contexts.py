"""
Scout's Context Registry
================

Env-driven wiring for the contexts available to Scout.
"""

from __future__ import annotations

import json
import logging
from os import getenv

from agno.tools import tool

from scout.context.provider import ContextProvider
from scout.context.web.exa import ExaBackend
from scout.context.web.exa_mcp import ExaMCPBackend
from scout.context.web.parallel import ParallelBackend
from scout.context.web.provider import WebContextProvider

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build Contexts
# ---------------------------------------------------------------------------


def build_contexts() -> list[ContextProvider]:
    """Build the registered contexts from env."""
    contexts: list[ContextProvider] = []
    web = _build_web()
    if web is not None:
        contexts.append(web)
        log.info("context: web")
    return contexts


def _build_web() -> WebContextProvider | None:
    try:
        if getenv("PARALLEL_API_KEY"):
            return WebContextProvider(backend=ParallelBackend())
        if getenv("EXA_API_KEY"):
            return WebContextProvider(backend=ExaBackend())
        return WebContextProvider(backend=ExaMCPBackend())
    except Exception:
        log.exception("context: web build failed; skipping")
        return None


# ---------------------------------------------------------------------------
# Runtime registry
# ---------------------------------------------------------------------------


_contexts: list[ContextProvider] = []


def publish_contexts(contexts: list[ContextProvider]) -> None:
    """Publish the context list so the rest of the process can see it.

    Explorer reads it via the ``explorer_tools`` callable on every run
    (``cache_callables=False`` on Explorer), so no agent mutation is
    needed here.
    """
    global _contexts
    _contexts = list(contexts)


def get_contexts() -> list[ContextProvider]:
    return list(_contexts)


@tool
async def list_contexts() -> str:
    """List registered contexts with current status.

    Returns:
        JSON list of ``{id, name, ok, detail}``.
    """
    rows = []
    for ctx in _contexts:
        try:
            s = await ctx.astatus()
            ok = s.ok
            detail = s.detail
        except Exception as exc:
            ok = False
            detail = f"{type(exc).__name__}: {exc}"
        rows.append({"id": ctx.id, "name": ctx.name, "ok": ok, "detail": detail})
    return json.dumps(rows)
