"""
Scout's Context Registry
========================

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
from scout.settings import default_model

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build Contexts
# ---------------------------------------------------------------------------


contexts: list[ContextProvider] = []


def build_contexts() -> list[ContextProvider]:
    """Build the registered contexts from env and cache them for the process."""
    contexts[:] = [_build_web()]
    log.info("context: web")
    return list(contexts)


def get_contexts() -> list[ContextProvider]:
    """Return the cached context list, building on first access."""
    if not contexts:
        build_contexts()
    return list(contexts)


def update_contexts(new_contexts: list[ContextProvider]) -> None:
    """Swap the cached context list in place. Used by eval fixtures."""
    contexts[:] = new_contexts


def _build_web() -> WebContextProvider:
    model = default_model()
    if getenv("PARALLEL_API_KEY"):
        return WebContextProvider(backend=ParallelBackend(), model=model)
    if getenv("EXA_API_KEY"):
        return WebContextProvider(backend=ExaBackend(), model=model)
    return WebContextProvider(backend=ExaMCPBackend(), model=model)


def status_row(ctx: ContextProvider) -> dict:
    """Row-shape summary of one context's current status."""
    try:
        s = ctx.status()
        return {"id": ctx.id, "name": ctx.name, "ok": s.ok, "detail": s.detail}
    except Exception as exc:
        return {"id": ctx.id, "name": ctx.name, "ok": False, "detail": f"{type(exc).__name__}: {exc}"}


async def astatus_row(ctx: ContextProvider) -> dict:
    """Async variant of ``status_row``."""
    try:
        s = await ctx.astatus()
        return {"id": ctx.id, "name": ctx.name, "ok": s.ok, "detail": s.detail}
    except Exception as exc:
        return {"id": ctx.id, "name": ctx.name, "ok": False, "detail": f"{type(exc).__name__}: {exc}"}


@tool
async def list_contexts() -> str:
    """List registered contexts with current status.

    Returns:
        JSON list of ``{id, name, ok, detail}``.
    """
    rows = [await astatus_row(ctx) for ctx in contexts]
    return json.dumps(rows)
