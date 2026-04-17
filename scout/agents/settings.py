"""Shared settings for all Scout agents — DB, knowledge bases."""

from db import create_knowledge, get_postgres_db

agent_db = get_postgres_db()
scout_knowledge = create_knowledge("Scout Knowledge", "scout_knowledge")
scout_learnings = create_knowledge("Scout Learnings", "scout_learnings")
