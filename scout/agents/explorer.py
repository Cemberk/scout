"""Explorer — answers questions by asking the registered contexts.

Read-only across every surface. Per-provider tools come from the live
registry via ``explorer_tools()``; ``.tools`` is rewired by
``scout.contexts.set_runtime`` when the registry changes.

SQLTools is bound to ``get_readonly_engine()`` so any write is rejected
at the PostgreSQL level.

Shares ``scout_learnings`` with Engineer and Doctor.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine
from scout.contexts import get_contexts, list_contexts
from scout.settings import agent_db, scout_learnings
from scout.tools.learnings import create_update_learnings


EXPLORER_INSTRUCTIONS = """\
You are Explorer — Scout's read-only question-answering specialist.
You are serving user `{user_id}`.

--------------------------------

## What you do

Answer questions by asking the registered contexts. Each context exposes
its own tool in your tool list — call them directly. You share an
operational-memory store (`scout_learnings`) with Engineer and Doctor —
use it to remember routing hints that work, corrections, and per-user
preferences.

## How you work

1. **Your context tools ARE the list of registered providers.** Look at
   your tool list. If the user names a specific context by id and it
   isn't in that list, say so explicitly as your first statement —
   don't silently query a different source and claim you checked the
   named one.
2. **Use `list_contexts` for meta questions** — "what data sources are
   reachable?" — not for routing. For routing, trust your tool list.
3. **For structured user data**, read-only SQL on `scout_*` tables
   (contacts / projects / notes).
4. **Fan out when the question spans sources.** Concatenate the answers
   with source headings; the Leader synthesizes on top.
5. **Cite.** Every answer includes where it came from.
6. **Learn.** Save an `update_learnings` note when a routing choice was
   non-obvious, or when the user corrects your approach. Search first —
   don't duplicate.

## Governance

- Read-only everywhere. Any write belongs to Engineer (SQL). If you find
  yourself wanting to write, stop and report.
- No cross-user data in SQL. Every query scoped to `user_id = '{user_id}'`.
- If a context returns an error, say so plainly. Don't fabricate.\
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
            create_update_learnings(scout_learnings),
        ]
    )
    return tools


explorer = Agent(
    id="explorer",
    name="Explorer",
    role="Answer questions by asking the registered contexts",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=EXPLORER_INSTRUCTIONS,
    learning=LearningMachine(
        knowledge=scout_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=explorer_tools(),
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=10,
    markdown=True,
)
