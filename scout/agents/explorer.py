"""
Explorer Agent
==============

Answers questions by asking the wiki + registered contexts (§4.1).
Read-only across every surface. Model picks which target to query,
informed by Learnings.

Explorer shares the ``scout_learnings`` memory store with Engineer and
Doctor. Its SQLTools is bound to ``get_readonly_engine()`` so any
INSERT / UPDATE / DELETE / DDL is rejected at the PostgreSQL level.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine
from scout.instructions import explorer_instructions
from scout.settings import agent_db, scout_learnings
from scout.tools.ask_context import ask_context, list_contexts
from scout.tools.learnings import create_update_learnings


def _explorer_tools() -> list:
    return [
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
        ask_context,
        list_contexts,
        create_update_learnings(scout_learnings),
    ]


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
    tools=_explorer_tools(),
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=10,
    markdown=True,
)
