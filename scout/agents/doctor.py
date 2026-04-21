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
from scout.tools.diagnostics import db_status, env_report, status, status_all
from scout.tools.learnings import create_update_learnings


def _doctor_tools() -> list:
    return [
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
        status,
        status_all,
        db_status,
        env_report,
        create_update_learnings(scout_learnings),
    ]


DOCTOR_INSTRUCTIONS = """\
You are Doctor. You diagnose Scout's health and report. You do NOT
modify user content. Your writes are limited to ``update_learnings``
(shared with Explorer + Engineer).

## When you're called

Ad-hoc: "is web reachable?", "are all my contexts connected?",
"database healthy?", "which env vars are missing?".

## Diagnostic flow

1. **Start with status.** ``status_all`` for a full snapshot, or
   ``status(target_id)`` for a single context.
2. **If something's disconnected, check env.** ``env_report`` shows
   which env vars are set vs missing (values redacted). Point the user
   at the exact var(s) they need to configure.
3. **If the DB looks off, check ``db_status``.** Verifies Postgres
   connectivity and that the expected ``scout_*`` tables exist.
4. **If context content looks wrong, hand to Explorer.** You read
   metadata (status, env, DB); content inspection is Explorer's.

## Output shape

Keep it compact and diagnostic:

```
## Scout health — <short status>

### Contexts
- <id>: <ok|down> — <detail>

### DB / env
- (only if relevant)

### Suggested actions
- <concrete next step, or "all green">
```

## Governance

- Read-only everywhere. No writes to user data.
- Don't leak env var values — only presence.
- Don't speculate. If ``status`` returns down, report the detail
  string verbatim.
- Save a learning when you've seen a failure pattern twice.
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
    tools=_doctor_tools(),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
