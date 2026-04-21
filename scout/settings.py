"""
Scout Settings
==============

Environment and runtime objects shared across agents.
"""

from db import get_postgres_db

agent_db = get_postgres_db()
