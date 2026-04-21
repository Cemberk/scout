"""
Doctor Agent
============

Diagnoses Scout's own health — context connections, DB, env. Read-only
everywhere; SQLTools is bound to ``get_readonly_engine()``.

Shares ``scout_learnings`` with Explorer and Engineer.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine
from scout.settings import agent_db, scout_learnings
from scout.tools.diagnostics import db_status, status, status_all
from scout.tools.learnings import create_update_learnings


def doctor_tools() -> list:
    return [
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
        status,
        status_all,
        db_status,
        create_update_learnings(scout_learnings),
    ]


DOCTOR_INSTRUCTIONS = """\
You are Doctor. You diagnose Scout's health; read-only everywhere.

- `status_all()` — snapshot of every context.
- `status(id)` — one context.
- `db_status()` — Postgres + `scout_*` tables.

If a context is down, report the `detail` string verbatim — it
typically names the missing env var. Save learnings on recurring
failure patterns.
"""

doctor = Agent(
    id="doctor",
    name="Doctor",
    role="Diagnoses Scout's own health — contexts + DB + env",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=DOCTOR_INSTRUCTIONS,
    learning=LearningMachine(
        knowledge=scout_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=doctor_tools(),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
