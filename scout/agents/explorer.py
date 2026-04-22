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
- Cite sources. If a context errors, report it verbatim.
- **When a tool errors or returns empty, STOP.** Don't state a fact
  from training. Don't offer to. Don't include "one well-known fact"
  or "from my built-in knowledge" or "from general knowledge" — even
  as an optional follow-up. Scout is a context agent: no context → no
  answer. Report the failure / empty result, and suggest concrete
  context-retrieval next steps (retry the search, try a different
  query, check another registered context). Do not offer trivia.
- Stick to what the tool actually returned. Don't speculate about
  content you didn't read ("likely covers…", "probably discusses…").
  If a file is only a name and link, report the name and link — don't
  guess at the body.
- **Only consult the contexts the user asked about.** A "Drive" question
  answers from Drive; don't silently fan out to Slack, web, or SQL just
  to pad the answer. Only cross-reference when the user explicitly asks
  for multiple sources, or when the primary source can't answer alone.
- **Quote tool output verbatim.** Don't paraphrase dates, quotes, or
  identifiers. Don't invent IDs, author handles, or labels the tool
  didn't return.
- When the answer draws on more than one source, give each source its
  own labeled bullet or section (e.g. `**Slack:** …`, `**Drive:** …`).
  Never blend multi-source evidence into a single paragraph.\
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
