"""
Database Context Provider
=========================

The user's CRM. Two namespaced tools:

- `query_crm` — natural-language reads of the `scout_*` tables.
- `update_crm` — natural-language writes (DDL + DML scoped to the
                 `scout` schema).

Two sub-agents under the hood so read paths never get the write
engine. The read sub-agent binds to `get_readonly_engine()` (PostgreSQL
rejects writes); the write sub-agent binds to `get_sql_engine()`, which
has a before-cursor hook that refuses DDL/DML against `public` / `ai`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agno.agent import Agent
from agno.tools.sql import SQLTools
from sqlalchemy import text

from db import SCOUT_SCHEMA, get_readonly_engine, get_sql_engine
from scout.context._utils import answer_from_run
from scout.context.mode import ContextMode
from scout.context.provider import Answer, ContextProvider, Status

if TYPE_CHECKING:
    from agno.models.base import Model


class DatabaseContextProvider(ContextProvider):
    """Read + write access to the `scout_*` tables via two tools."""

    def __init__(
        self,
        *,
        id: str = "crm",
        name: str = "CRM",
        mode: ContextMode = ContextMode.default,
        model: Model | None = None,
    ) -> None:
        super().__init__(id=id, name=name, mode=mode, model=model)
        self._read_agent: Agent | None = None
        self._write_agent: Agent | None = None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Status:
        try:
            engine = get_readonly_engine()
            with engine.connect() as conn:
                count = conn.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = :schema AND table_name LIKE 'scout\\_%' ESCAPE '\\'"
                    ),
                    {"schema": SCOUT_SCHEMA},
                ).scalar()
        except Exception as exc:
            return Status(ok=False, detail=f"{type(exc).__name__}: {exc}")
        return Status(ok=True, detail=f"{count} scout_* table(s)")

    async def astatus(self) -> Status:
        return self.status()

    # ------------------------------------------------------------------
    # Query / update
    # ------------------------------------------------------------------

    def query(self, question: str) -> Answer:
        return answer_from_run(self._ensure_read_agent().run(question))

    async def aquery(self, question: str) -> Answer:
        return answer_from_run(await self._ensure_read_agent().arun(question))

    def update(self, instruction: str) -> Answer:
        return answer_from_run(self._ensure_write_agent().run(instruction))

    async def aupdate(self, instruction: str) -> Answer:
        return answer_from_run(await self._ensure_write_agent().arun(instruction))

    def instructions(self) -> str:
        if self.mode == ContextMode.tools:
            return (
                f"`{self.name}`: use `run_sql_query` directly against the `scout` schema. "
                "NOTE: mode=tools does NOT preserve the read/write split — both read "
                "and write SQLTools instances are exposed. Prefer the default two-tool "
                "surface (`query_crm` / `update_crm`) unless you have a reason."
            )
        return (
            f"`{self.name}`: call `{self.query_tool_name}(question)` to read the user's "
            f"contacts/projects/notes, or `{self.update_tool_name}(instruction)` to save/update "
            "them. Writes are scoped to the `scout` schema."
        )

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    def _default_tools(self) -> list:
        return [self._query_tool(), self._update_tool()]

    def _all_tools(self) -> list:
        # Caveat: mode=tools skips the read/write sub-agent split, so the
        # calling agent sees both SQLTools instances. The scout-schema
        # guard still fires for writes to public/ai.
        return [
            SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
            SQLTools(db_engine=get_sql_engine(), schema=SCOUT_SCHEMA),
        ]

    # ------------------------------------------------------------------
    # Sub-agents
    # ------------------------------------------------------------------

    def _ensure_read_agent(self) -> Agent:
        if self._read_agent is None:
            self._read_agent = self._build_read_agent()
        return self._read_agent

    def _ensure_write_agent(self) -> Agent:
        if self._write_agent is None:
            self._write_agent = self._build_write_agent()
        return self._write_agent

    def _build_read_agent(self) -> Agent:
        return Agent(
            id="crm-read",
            name="CRM Read",
            role="Answer questions about the user's CRM data",
            model=self.model,
            instructions=_READ_INSTRUCTIONS,
            tools=[SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA)],
            markdown=True,
        )

    def _build_write_agent(self) -> Agent:
        return Agent(
            id="crm-write",
            name="CRM Write",
            role="Modify the user's CRM data",
            model=self.model,
            instructions=_WRITE_INSTRUCTIONS,
            tools=[SQLTools(db_engine=get_sql_engine(), schema=SCOUT_SCHEMA)],
            markdown=True,
        )


_READ_INSTRUCTIONS = """\
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


_WRITE_INSTRUCTIONS = """\
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
5. **Report what you did in a single sentence.**
   Example: "Saved contact Alice Chen (id=47)." or "Created scout_coffee_orders and logged your first order (id=1)."
   Don't recite the full row or explain the SQL you ran.
6. **DROP requires explicit user confirmation.** Don't drop tables on a
   first ask.

## Safety

You can only write inside the `scout` schema. `public` and `ai` are
rejected at the engine level — attempts will error loudly. If the user
asks for a table in another schema, explain that writes are scoped to
`scout` and propose a `scout_*` name instead.
"""
