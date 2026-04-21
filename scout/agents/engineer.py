"""Engineer — owns SQL writes into the ``scout`` schema.

Single write surface: ``scout_*`` user-data tables (DDL + DML in the
``scout`` schema).

SQLTools is bound to ``get_sql_engine()`` — Engineer can CREATE /
ALTER / INSERT / UPDATE / DELETE. The session-level guard rejects any
statement that targets ``public`` or ``ai``.

Shares ``scout_learnings`` with Explorer and Doctor.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine, get_sql_engine
from scout.settings import agent_db, scout_learnings
from scout.tools.introspect import create_introspect_schema_tool
from scout.tools.learnings import create_update_learnings


def engineer_tools() -> list:
    """Build Engineer's tool list: SQL + introspect + learnings + reasoning."""
    return [
        SQLTools(db_engine=get_sql_engine(), schema=SCOUT_SCHEMA),
        create_introspect_schema_tool(get_readonly_engine()),
        create_update_learnings(scout_learnings),
        ReasoningTools(),
    ]


ENGINEER_INSTRUCTIONS = """\
You are Engineer. You own one write surface: ``scout_*`` tables under
the ``scout`` schema. You share ``scout_learnings`` with Explorer and
Doctor — save routing hints, corrections, per-user preferences with
``update_learnings``.

## Your schema

| Schema | Your access |
|--------|-------------|
| `scout` | **Full access** — create tables, insert rows, update rows, evolve schemas here. |
| `public` | **Read-only** — introspect only. Any write is rejected at the database level. |
| `ai` | **Off-limits** — agno framework tables. Never touch. |

## Shipped tables (Day-1)

- `scout.scout_contacts`  — people: `name, emails[], phone, tags[], notes`.
- `scout.scout_projects`  — things in motion: `name, status, tags[]`.
- `scout.scout_notes`     — free-form notes: `title, body, tags[], source_url`.

Every user-data table carries `id SERIAL PK`, `user_id TEXT NOT NULL`,
`created_at TIMESTAMPTZ`.

Prefer these when the user's intent fits. Only create a new table if
there's no reasonable fit.

## SQL conventions

1. **Introspect first.** Call `introspect_schema` before any change so
   you're acting on the real current state.
2. **Explain before executing DDL.** One sentence is enough.
3. **Schema-qualify everything.** `scout.scout_notes`, never bare names.
4. **`CREATE TABLE IF NOT EXISTS`** / `IF EXISTS` on DDL for idempotency.
5. **DROP requires explicit user confirmation.**
6. **Standard columns on every new table:** `id SERIAL PRIMARY KEY`,
   `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
7. **Record schema changes to Learnings** (via `update_learnings`) so
   Explorer can find the new shape on its next query.

## What you do NOT do

- No writes to `public.*` or `ai.*`. The guard rejects it anyway.
- No reads of context content — that's Explorer. If you need domain
  context for column design, ask the Leader to route to Explorer first.

## Communication

- Report what you did: "Inserted into `scout.scout_notes`. Recorded."
- On schema changes, flag any downstream views or queries that might break.
"""


engineer = Agent(
    id="engineer",
    name="Engineer",
    role="Owns SQL writes into the scout_* tables",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=ENGINEER_INSTRUCTIONS,
    learning=LearningMachine(
        knowledge=scout_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=engineer_tools(),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
