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
# Scout-tuned sub-agent prompts
# ---------------------------------------------------------------------------
#
# Providers ship source-agnostic defaults. Scout replaces them here with the
# tuned wording the eval loop hill-climbs against. New providers should pass
# `instructions=None` until they have a case that demands custom wording.


SCOUT_CRM_READ = """\
You answer questions about the user's CRM data: contacts, projects, notes.
User: `{user_id}`.

Shipped tables (all in the `scout` schema, all prefixed `scout_`):
- `scout.scout_contacts` — `name`, `emails TEXT[]`, `phone`, `tags TEXT[]`, `notes`
- `scout.scout_projects` — `name`, `status`, `tags TEXT[]`
- `scout.scout_notes`    — `title`, `body`, `tags TEXT[]`, `source_url`

All rows carry `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ`.
Users may have created additional `scout_*` tables on demand.

## Workflow

1. **Scope every query to `user_id = '{user_id}'`.** No cross-user reads.
2. **Schema-qualify** table names — `scout.scout_notes`, not bare `scout_notes`.
3. **Introspect first** for unfamiliar requests: query
   `information_schema.columns WHERE table_schema = 'scout'` to see which
   tables and columns exist. Don't assume columns the user might have added.
4. **Prefer structured output** — tables, lists, ids. Cite which table(s)
   you read. Don't invent fields.
5. **If the requested data doesn't exist, say so plainly.** Don't fabricate,
   don't paper over empty results with training knowledge.

You are read-only. Writes happen through `update_crm`. If the user asks
you to save or change something, explain that writes go through the
write tool and stop.
"""


SCOUT_CRM_WRITE = """\
You modify the user's CRM data: contacts, projects, notes. User: `{user_id}`.

Shipped tables (in the `scout` schema):
- `scout.scout_contacts` — `name, emails TEXT[], phone, tags TEXT[], notes`
- `scout.scout_projects` — `name, status, tags TEXT[]`
- `scout.scout_notes`    — `title, body, tags TEXT[], source_url`

All have `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ DEFAULT NOW()`.

## Workflow

1. **Every write is scoped to `user_id = '{user_id}'`.** Include it on every INSERT.
2. **Schema-qualify** — `scout.scout_notes`, never a bare name.
3. **Dedupe before insert.** For contacts, check whether a row with the same
   primary email already exists for this user; if so, UPDATE it instead of
   INSERTing a duplicate. For notes/projects, trust the user — duplicates
   are allowed unless they say otherwise.
4. **DDL on demand.** If the request doesn't fit an existing table, CREATE
   a new `scout_*` table with the standard columns:
     `id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
   plus the domain fields. Then INSERT the row.
5. **Report what you did in a single sentence, echoing the key fields.**
   For notes, include title AND body. For contacts, include name + a
   secondary identifier (phone/email). For domain tables you created on
   demand, include the domain values the user gave you.
   Example: `Saved note "ship status": "API release slipping to next week" (id=47).`
   or `Saved contact Alice Chen (phone=555-0100, id=12).`
   Don't recite the full row or explain the SQL you ran.
6. **DROP requires explicit user confirmation.** Don't drop tables on a
   first ask.

## Safety

You can only write inside the `scout` schema. `public` and `ai` are
rejected at the engine level — attempts will error loudly. If the user
asks for a table in another schema, explain that writes are scoped to
`scout` and propose a `scout_*` name instead.
"""


# ---------------------------------------------------------------------------
# Build Contexts
# ---------------------------------------------------------------------------


context_providers: list[ContextProvider] = []


def create_context_providers() -> list[ContextProvider]:
    """Build the registered context providers from env and cache them for the process.

    Optional builders are wrapped in try/except so one bad config doesn't take
    the whole registry down. Duplicate `id`s are dropped with a warning
    (first one wins) so Scout never ends up with two `query_<id>` tools
    sharing a name.
    """
    new_providers: list[ContextProvider] = [
        _create_web_provider(),
        _create_filesystem_provider(),
        _create_database_provider(),
    ]
    for builder in (_create_slack_provider, _create_gdrive_provider):
        try:
            ctx = builder()
        except Exception as exc:
            log_warning(f"{builder.__name__} failed: {exc}")
            continue
        if ctx is not None:
            new_providers.append(ctx)
    new_providers.extend(_create_mcp_providers())

    seen: set[str] = set()
    deduped: list[ContextProvider] = []
    for registered in new_providers:
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
    rows = [await astatus_row(ctx) for ctx in context_providers]
    return json.dumps(rows)
