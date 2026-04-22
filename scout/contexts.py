"""
Scout's Context Registry
========================

Wiring for the contexts available to Scout. Web and filesystem are always on;
Slack and Google Drive light up when their env vars are set.
"""

from __future__ import annotations

import asyncio
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
from scout.context.mode import ContextMode
from scout.context.provider import ContextProvider
from scout.context.slack import SlackContextProvider
from scout.context.web.exa import ExaBackend
from scout.context.web.exa_mcp import ExaMCPBackend
from scout.context.web.parallel import ParallelBackend
from scout.context.web.provider import WebContextProvider
from scout.instructions import SCOUT_CRM_READ, SCOUT_CRM_WRITE
from scout.settings import default_model

# Filesystem context root — the scout repo. Edit this one line to scope
# Scout to a different directory.
FS_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Create Context Providers
# ---------------------------------------------------------------------------


context_providers: list[ContextProvider] = []


def create_context_providers() -> list[ContextProvider]:
    """Build the registered context providers from env and cache them for the process.

    Optional builders are wrapped in try/except so one bad config doesn't take
    the whole registry down. Duplicate `id`s are dropped with a warning
    (first one wins) so Scout never ends up with two `query_<id>` tools
    sharing a name.
    """
    configured_providers: list[ContextProvider] = [
        _create_web_provider(),
        _create_filesystem_provider(),
        _create_database_provider(),
    ]
    for factory in (_create_slack_provider, _create_gdrive_provider):
        try:
            provider = factory()
        except Exception as exc:
            log_warning(f"{factory.__name__} failed: {exc}")
            continue
        if provider is not None:
            configured_providers.append(provider)
    configured_providers.extend(_create_mcp_providers())

    seen: set[str] = set()
    deduped: list[ContextProvider] = []
    for registered in configured_providers:
        if registered.id in seen:
            log_warning(
                f"context id {registered.id!r} already registered; skipping duplicate ({type(registered).__name__})"
            )
            continue
        seen.add(registered.id)
        deduped.append(registered)

    context_providers[:] = deduped
    _log_context_providers(deduped)
    return list(context_providers)


def _log_context_providers(ctxs: list[ContextProvider]) -> None:
    """Log the resolved provider set with each provider's status detail."""
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


def get_context_providers() -> list[ContextProvider]:
    """Return the cached provider list, building on first access."""
    if not context_providers:
        create_context_providers()
    return list(context_providers)


def update_context_providers(new_providers: list[ContextProvider]) -> None:
    """Swap the cached provider list in place. Used by eval fixtures."""
    context_providers[:] = new_providers


async def close_context_providers() -> None:
    """Release resources held by every cached provider.

    Providers that hold resources (MCP sessions, watch streams) override
    `aclose()`; the base class default is a no-op. `return_exceptions=True`
    so one stuck teardown can't block others on the way down.
    """
    providers = list(get_context_providers())
    if not providers:
        return
    results = await asyncio.gather(
        *(p.aclose() for p in providers),
        return_exceptions=True,
    )
    for provider, outcome in zip(providers, results, strict=True):
        if isinstance(outcome, BaseException):
            log_warning(f"context {provider.id!r} aclose raised {type(outcome).__name__}: {outcome}")


async def prewarm_context_providers() -> None:
    """Eagerly initialize providers that need async setup before
    ``get_tools()`` returns usable tools (e.g. ``mode=tools`` MCP servers
    whose function list is only populated after ``_connect()``).
    """
    providers = list(get_context_providers())
    if not providers:
        return
    results = await asyncio.gather(
        *(p.aprewarm() for p in providers),
        return_exceptions=True,
    )
    for provider, outcome in zip(providers, results, strict=True):
        if isinstance(outcome, BaseException):
            log_warning(f"context {provider.id!r} aprewarm raised {type(outcome).__name__}: {outcome}")


def _create_web_provider() -> WebContextProvider:
    model = default_model()
    if getenv("PARALLEL_API_KEY"):
        return WebContextProvider(backend=ParallelBackend(), model=model)
    if getenv("EXA_API_KEY"):
        return WebContextProvider(backend=ExaBackend(), model=model)
    return WebContextProvider(backend=ExaMCPBackend(), model=model)


def _create_filesystem_provider() -> FilesystemContextProvider:
    return FilesystemContextProvider(root=FS_ROOT, model=default_model())


def _create_database_provider() -> DatabaseContextProvider:
    return DatabaseContextProvider(
        id="crm",
        name="CRM",
        sql_engine=get_sql_engine(),
        readonly_engine=get_readonly_engine(),
        schema=SCOUT_SCHEMA,
        read_instructions=SCOUT_CRM_READ,
        write_instructions=SCOUT_CRM_WRITE,
        model=default_model(),
    )


def _create_slack_provider() -> SlackContextProvider | None:
    if not (getenv("SLACK_BOT_TOKEN") or getenv("SLACK_TOKEN")):
        return None
    return SlackContextProvider(model=default_model())


def _create_gdrive_provider() -> GDriveContextProvider | None:
    if not getenv("GOOGLE_SERVICE_ACCOUNT_FILE"):
        return None
    return GDriveContextProvider(model=default_model())


def _create_mcp_providers() -> list[MCPContextProvider]:
    """Registered MCP servers.

    Add a ``MCPContextProvider(...)`` entry per server. Pull secrets
    from env via ``getenv(...)`` inside the constructor call. See
    ``docs/MCP_CONNECT.md``.
    """
    return [
        MCPContextProvider(
            server_name="time",
            transport="stdio",
            command="uvx",
            args=["mcp-server-time"],
            mode=ContextMode.tools,
            model=default_model(),
        ),
    ]


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
    rows = [await astatus_row(ctx) for ctx in context_providers]
    return json.dumps(rows)
