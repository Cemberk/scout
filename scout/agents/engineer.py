"""Engineer — owns SQL writes into the ``scout`` schema.

Single write surface: ``scout_*`` user-data tables (DDL + DML in the
``scout`` schema).

SQLTools is bound to ``get_sql_engine()`` — Engineer can CREATE /
ALTER / INSERT / UPDATE / DELETE. The session-level guard rejects any
statement that targets ``public`` or ``ai``.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_sql_engine
from scout.settings import agent_db

ENGINEER_INSTRUCTIONS = """\
You are Engineer. You own writes to the `scout` schema.

## Tables (Day-1)

- `scout.scout_contacts` — `name, emails[], phone, tags[], notes`
- `scout.scout_projects` — `name, status, tags[]`
- `scout.scout_notes`    — `title, body, tags[], source_url`

All tables have `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ`.
Prefer these when intent fits; create new `scout_*` tables only when it doesn't.

## Rules

- **Write only to `scout`.** `public` is read-only; `ai` is off-limits.
- **Schema-qualify everything.** `scout.scout_notes`, never bare names.
- **Introspect before DDL.** Query `information_schema.columns` first.
- **DROP requires explicit user confirmation.**
- **Standard columns on new tables:** `id SERIAL PRIMARY KEY`,
  `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
"""


engineer = Agent(
    id="engineer",
    name="Engineer",
    role="Owns SQL writes into the scout_* tables",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=ENGINEER_INSTRUCTIONS,
    tools=[SQLTools(db_engine=get_sql_engine(), schema=SCOUT_SCHEMA)],
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
