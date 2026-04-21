"""
Scout Settings
==============

DB-dependent runtime objects shared across agents.
"""

from db import create_knowledge, get_postgres_db

agent_db = get_postgres_db()
scout_learnings = create_knowledge("Scout Learnings", "scout_learnings")
