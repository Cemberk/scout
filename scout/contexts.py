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

from scout.context.fs import FilesystemContextProvider
from scout.context.gdrive import GDriveContextProvider
from scout.context.provider import ContextProvider
from scout.context.slack import SlackContextProvider
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
    """Build the registered contexts from env and cache them for the process.

    Optional builders are wrapped in try/except so one bad config doesn't take
    the whole registry down. Duplicate `id`s are dropped with a warning
    (first one wins) so Explorer never ends up with two `query_<id>` tools
    sharing a name.
    """
    new_contexts: list[ContextProvider] = [_build_web()]
    for builder in (_build_filesystem, _build_slack, _build_gdrive):
        try:
            ctx = builder()
        except Exception as exc:
            log.warning("%s failed: %s", builder.__name__, exc)
            continue
        if ctx is not None:
            new_contexts.append(ctx)

    seen: set[str] = set()
    deduped: list[ContextProvider] = []
    for registered in new_contexts:
        if registered.id in seen:
            log.warning(
                "context id %r already registered; skipping duplicate (%s)",
                registered.id,
                type(registered).__name__,
            )
            continue
        seen.add(registered.id)
        deduped.append(registered)

    contexts[:] = deduped
    log.info("contexts: %s", [c.id for c in deduped])
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


def _build_slack() -> SlackContextProvider | None:
    if not (getenv("SLACK_BOT_TOKEN") or getenv("SLACK_TOKEN")):
        return None
    return SlackContextProvider(model=default_model())


def _build_gdrive() -> GDriveContextProvider | None:
    if not getenv("GOOGLE_SERVICE_ACCOUNT_FILE"):
        return None
    return GDriveContextProvider(model=default_model())


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
