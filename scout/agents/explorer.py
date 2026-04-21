"""Explorer — answers questions by asking the registered contexts.

Read-only across every surface. ``tools=explorer_tools`` (a callable,
not its result) so agno re-resolves the per-provider tools on every
run from the live registry in ``scout.contexts``. ``cache_callables``
is off — the factory is cheap and we want fixture swaps in evals to
take effect immediately.

SQLTools is bound to ``get_readonly_engine()`` so any write is rejected
at the PostgreSQL level.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine
from scout.contexts import get_contexts, list_contexts
from scout.settings import agent_db, default_model

EXPLORER_INSTRUCTIONS = """\
You are Explorer — Scout's read-only specialist. User: `{user_id}`.

Answer by calling the `query_<id>` tools for registered contexts, or
read-only SQL on `scout_*` tables for structured user data. Use
`list_contexts` for meta questions only.

Rules:
- If the user names a context that isn't in your tool list, say so as
  your first statement. Don't silently ask a different source.
- Scope every SQL query to `user_id = '{user_id}'`.
- Cite sources. If a context errors, report it verbatim. Don't fabricate.\
"""


def explorer_tools() -> list:
    """Build Explorer's tool list from the current registry."""
    tools: list = []
    for ctx in get_contexts():
        tools.extend(ctx.get_tools())
    tools.extend(
        [
            SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
            list_contexts,
        ]
    )
    return tools


explorer = Agent(
    id="explorer",
    name="Explorer",
    role="Answer questions by asking the registered contexts",
    model=default_model(),
    db=agent_db,
    instructions=EXPLORER_INSTRUCTIONS,
    tools=explorer_tools,
    cache_callables=False,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)
