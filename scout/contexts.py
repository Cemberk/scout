"""
Scout's Context Registry
========================

Env-driven wiring for the contexts available to Scout.
"""

from __future__ import annotations

import json
import logging
from os import getenv
from pathlib import Path

import yaml
from agno.tools import tool

from scout.context.fs import FilesystemContextProvider
from scout.context.mcp import MCPContextProvider
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
    new_contexts: list[ContextProvider] = [_build_web()]
    fs = _build_filesystem()
    if fs is not None:
        new_contexts.append(fs)
    new_contexts.extend(_build_mcp_servers())
    contexts[:] = new_contexts
    log.info("contexts: %s", [c.id for c in new_contexts])
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


def _build_filesystem() -> FilesystemContextProvider | None:
    root = getenv("SCOUT_FS_ROOT")
    if not root:
        return None
    return FilesystemContextProvider(root=root, model=default_model())


_MCP_ENTRY_FIELDS = {"id", "name", "command", "url", "transport", "env"}


def _build_mcp_servers() -> list[MCPContextProvider]:
    path = getenv("SCOUT_MCP_CONFIG")
    if not path:
        return []
    try:
        entries = yaml.safe_load(Path(path).read_text()) or []
    except Exception as exc:
        log.warning("MCP config at %s unreadable: %s", path, exc)
        return []
    if not isinstance(entries, list):
        log.warning("MCP config at %s: expected a YAML list at top level", path)
        return []

    providers: list[MCPContextProvider] = []
    model = default_model()
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry:
            log.warning("MCP entry missing `id` (or not a mapping): %s", entry)
            continue
        kwargs = {k: v for k, v in entry.items() if k in _MCP_ENTRY_FIELDS}
        try:
            providers.append(MCPContextProvider(model=model, **kwargs))
        except Exception as exc:
            log.warning("MCP entry %s failed to build: %s", entry.get("id"), exc)
    return providers


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
