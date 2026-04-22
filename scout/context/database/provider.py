"""
Database Context Provider
=========================

A namespaced read/write surface over any SQL database. Two tools:

- `query_<id>` — natural-language reads, backed by a sub-agent bound
                 to a readonly engine.
- `update_<id>` — natural-language writes, backed by a sub-agent bound
                  to a writable engine.

Two sub-agents so the read path never sees the write engine. Callers
supply both engines and the schema the provider is scoped to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agno.agent import Agent
from agno.tools.sql import SQLTools
from sqlalchemy import text

from scout.context._utils import answer_from_run
from scout.context.mode import ContextMode
from scout.context.provider import Answer, ContextProvider, Status

if TYPE_CHECKING:
    from agno.models.base import Model
    from sqlalchemy.engine import Engine


class DatabaseContextProvider(ContextProvider):
    """Read + write access to a SQL schema via two tools."""

    def __init__(
        self,
        *,
        id: str,
        name: str,
        sql_engine: Engine,
        readonly_engine: Engine,
        schema: str,
        read_instructions: str | None = None,
        write_instructions: str | None = None,
        mode: ContextMode = ContextMode.default,
        model: Model | None = None,
    ) -> None:
        super().__init__(id=id, name=name, mode=mode, model=model)
        self.sql_engine = sql_engine
        self.readonly_engine = readonly_engine
        self.schema = schema
        self.read_instructions_text = (
            read_instructions if read_instructions is not None else DEFAULT_READ_INSTRUCTIONS
        )
        self.write_instructions_text = (
            write_instructions if write_instructions is not None else DEFAULT_WRITE_INSTRUCTIONS
        )
        self._read_agent: Agent | None = None
        self._write_agent: Agent | None = None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Status:
        try:
            with self.readonly_engine.connect() as conn:
                count = conn.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = :schema"
                    ),
                    {"schema": self.schema},
                ).scalar()
        except Exception as exc:
            return Status(ok=False, detail=f"{type(exc).__name__}: {exc}")
        return Status(ok=True, detail=f"{count} table(s) in {self.schema}")

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
                f"`{self.name}`: read-only `run_sql_query` against the `{self.schema}` schema. "
                "Writes require mode=default (two-tool surface)."
            )
        return (
            f"`{self.name}`: call `{self.query_tool_name}(question)` to read data in the "
            f"`{self.schema}` schema, or `{self.update_tool_name}(instruction)` to modify it."
        )

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    def _default_tools(self) -> list:
        return [self._query_tool(), self._update_tool()]

    def _all_tools(self) -> list:
        # mode=tools returns only the readonly SQLTools. The read/write
        # split the default sub-agent mode provides doesn't flatten into a
        # single tool list cleanly, and silent write exposure is the wrong
        # default. Writes require mode=default (two-tool surface:
        # query_<id> / update_<id>) or explicit instantiation of a second
        # writable provider.
        return [SQLTools(db_engine=self.readonly_engine, schema=self.schema)]

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
            id=f"{self.id}-read",
            name=f"{self.name} Read",
            role=f"Answer questions about data in the {self.schema} schema",
            model=self.model,
            instructions=self.read_instructions_text.replace("{schema}", self.schema),
            tools=[SQLTools(db_engine=self.readonly_engine, schema=self.schema)],
            markdown=True,
        )

    def _build_write_agent(self) -> Agent:
        return Agent(
            id=f"{self.id}-write",
            name=f"{self.name} Write",
            role=f"Modify data in the {self.schema} schema",
            model=self.model,
            instructions=self.write_instructions_text.replace("{schema}", self.schema),
            tools=[SQLTools(db_engine=self.sql_engine, schema=self.schema)],
            markdown=True,
        )


DEFAULT_READ_INSTRUCTIONS = """\
You answer questions about data in the `{schema}` schema. User: `{user_id}`.

## Workflow

1. **Scope every query to `user_id = '{user_id}'`.** No cross-user reads.
2. **Schema-qualify** table names — `{schema}.<table>`, not a bare name.
3. **Introspect first** for unfamiliar requests: query
   `information_schema.columns WHERE table_schema = '{schema}'` to see which
   tables and columns exist.
4. **Prefer structured output** — tables, lists, ids. Cite which table(s)
   you read. Don't invent fields.
5. **If the requested data doesn't exist, say so plainly.** Don't fabricate,
   don't paper over empty results with training knowledge.

You are read-only. Writes happen through the update tool. If the user asks
you to save or change something, explain that writes go through the write
tool and stop.
"""


DEFAULT_WRITE_INSTRUCTIONS = """\
You modify data in the `{schema}` schema. User: `{user_id}`.

## Workflow

1. **Every write is scoped to `user_id = '{user_id}'`.** Include it on every INSERT.
2. **Schema-qualify** — `{schema}.<table>`, never a bare name.
3. **DDL on demand.** If the request doesn't fit an existing table, CREATE
   a new table in `{schema}` with the standard columns:
     `id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
   plus the domain fields. Then INSERT the row.
4. **Report what you did concisely, echoing the key fields** the user gave
   you. Don't recite the full row or explain the SQL you ran.
5. **DROP requires explicit user confirmation.** Don't drop tables on a
   first ask.

## Safety

Writes are scoped to the `{schema}` schema — the engine enforces this
boundary and requests outside it will error. If the user asks for a table
in another schema, explain the scope and propose a `{schema}` name instead.
"""
