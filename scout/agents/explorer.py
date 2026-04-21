"""Explorer — answers questions by asking the wiki + registered contexts.

Read-only across every surface. Per-provider ``query_<id>`` tools are
built from the live registry via ``explorer_tools()``; Explorer's
``.tools`` list is rewired by ``scout.tools.ask_context.set_runtime``
when the registry changes.

SQLTools is bound to ``get_readonly_engine()`` so any
INSERT / UPDATE / DELETE / DDL is rejected at the PostgreSQL level.

Shares the ``scout_learnings`` memory store with Engineer and Doctor.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine
from scout.instructions import explorer_instructions
from scout.settings import agent_db, scout_learnings
from scout.tools.ask_context import get_contexts, get_wiki, list_contexts
from scout.tools.learnings import create_update_learnings


def explorer_tools() -> list:
    """Build Explorer's tool list from the current registry."""
    tools: list = []
    wiki = get_wiki()
    if wiki is not None:
        tools.extend(wiki.get_tools())
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
    role="Answer questions by asking the wiki + registered contexts",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=explorer_instructions(),
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
