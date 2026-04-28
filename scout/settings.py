"""
Scout Settings
==============

Environment and runtime objects shared across agents.
"""

from agno.models.openai import OpenAIResponses

from db import create_knowledge, get_postgres_db

agent_db = get_postgres_db()

# Cross-session learning store. Vector-embedded snippets of patterns Scout
# picks up over time (preferences, recurring conventions). Pulled into
# context by the agent. Scout writes new entries via
# `save_learning` and recalls related ones via `search_learnings`.
scout_learnings = create_knowledge("Scout Learnings", "scout_learnings")


def default_model() -> OpenAIResponses:
    """Fresh model instance per agent — avoids shared-state footguns."""
    return OpenAIResponses(id="gpt-5.5")
