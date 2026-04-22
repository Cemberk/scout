"""
Scout's Context Registry
========================

Wiring for the contexts available to Scout. Web and filesystem are always on;
Slack and Google Drive light up when their env vars are set.
"""

from __future__ import annotations

import json
from os import getenv
from pathlib import Path

from agno.tools import tool
from agno.utils.log import log_info, log_warning

from db import SCOUT_SCHEMA, get_readonly_engine, get_sql_engine
from scout.context.database import DatabaseContextProvider
from scout.context.fs import FilesystemContextProvider
from scout.context.gdrive import GDriveContextProvider
from scout.context.mcp import MCPContextProvider
from scout.context.mcp.config import parse_mcp_env
from scout.context.provider import ContextProvider
from scout.context.slack import SlackContextProvider
from scout.context.web.exa import ExaBackend
from scout.context.web.exa_mcp import ExaMCPBackend
from scout.context.web.parallel import ParallelBackend
from scout.context.web.provider import WebContextProvider
from scout.settings import default_model

# Filesystem context root — the scout repo. Edit this one line to scope
# Scout to a different directory.
FS_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Build Contexts
# ---------------------------------------------------------------------------


contexts: list[ContextProvider] = []


def build_contexts() -> list[ContextProvider]:
    """Build the registered contexts from env and cache them for the process.

    Optional builders are wrapped in try/except so one bad config doesn't take
    the whole registry down. Duplicate `id`s are dropped with a warning
    (first one wins) so Explorer never ends up with two `query_<id>` tools
    sharing a name.
    """
    new_contexts: list[ContextProvider] = [_build_web(), _build_filesystem(), _build_database()]
    for builder in (_build_slack, _build_gdrive):
        try:
            ctx = builder()
        except Exception as exc:
            log_warning(f"{builder.__name__} failed: {exc}")
            continue
        if ctx is not None:
            new_contexts.append(ctx)
    new_contexts.extend(_build_mcp_providers())

    seen: set[str] = set()
    deduped: list[ContextProvider] = []
    for registered in new_contexts:
        if registered.id in seen:
            log_warning(
                f"context id {registered.id!r} already registered; skipping duplicate ({type(registered).__name__})"
            )
            continue
        seen.add(registered.id)
        deduped.append(registered)

    contexts[:] = deduped
    _log_contexts(deduped)
    return list(contexts)


def _log_contexts(ctxs: list[ContextProvider]) -> None:
    """Log the resolved context set with each provider's status detail."""
    if not ctxs:
        log_info("Context Providers: (none)")
        return
    width = max(len(c.id) for c in ctxs)
    lines = ["Context Providers:"]
    for c in ctxs:
        try:
            detail = c.status().detail
        except Exception as exc:
            detail = f"<status failed: {type(exc).__name__}>"
        lines.append(f"  {c.id:<{width}}  {detail}")
    log_info("\n".join(lines))


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


def _build_filesystem() -> FilesystemContextProvider:
    return FilesystemContextProvider(root=FS_ROOT, model=default_model())


def _build_database() -> DatabaseContextProvider:
    return DatabaseContextProvider(
        id="crm",
        name="CRM",
        sql_engine=get_sql_engine(),
        readonly_engine=get_readonly_engine(),
        schema=SCOUT_SCHEMA,
        model=default_model(),
    )


def _build_slack() -> SlackContextProvider | None:
    if not (getenv("SLACK_BOT_TOKEN") or getenv("SLACK_TOKEN")):
        return None
    return SlackContextProvider(model=default_model())


def _build_gdrive() -> GDriveContextProvider | None:
    if not getenv("GOOGLE_SERVICE_ACCOUNT_FILE"):
        return None
    return GDriveContextProvider(model=default_model())


def _build_mcp_providers() -> list[MCPContextProvider]:
    """One `MCPContextProvider` per slug in `MCP_SERVERS`.

    Misconfigured slugs log a warning and are skipped — one bad server
    can't take the rest down.
    """
    raw = getenv("MCP_SERVERS", "")
    slugs = [s.strip() for s in raw.split(",") if s.strip()]
    providers: list[MCPContextProvider] = []
    for slug in slugs:
        try:
            cfg = parse_mcp_env(slug)
            providers.append(MCPContextProvider(**cfg, model=default_model()))
        except Exception as exc:
            log_warning(f"MCP server {slug!r} misconfigured: {type(exc).__name__}: {exc}")
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
