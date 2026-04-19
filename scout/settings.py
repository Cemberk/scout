"""
Scout Settings
==============

Environment-derived constants and DB-dependent runtime objects used
across Scout. DB objects are created at import time so every agent
shares the same instance.

Paths live in ``scout.paths``. Feature/source-enablement is derived
at call sites from the relevant env vars below.
"""

from os import getenv
from pathlib import Path

from db import create_knowledge, get_postgres_db

# --- Web research: Parallel (premium) or keyless Exa MCP fallback ----------
PARALLEL_API_KEY = getenv("PARALLEL_API_KEY", "")
EXA_API_KEY = getenv("EXA_API_KEY", "")
EXA_MCP_URL = (
    f"https://mcp.exa.ai/mcp?exaApiKey={EXA_API_KEY}&tools=web_search_exa,web_fetch_exa"
    if EXA_API_KEY
    else "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
)

# --- Slack (Scout's own bot identity) --------------------------------------
SLACK_TOKEN = getenv("SLACK_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")

# --- Google (Gmail + Calendar + Drive) -------------------------------------
GOOGLE_CLIENT_ID = getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_PROJECT_ID = getenv("GOOGLE_PROJECT_ID", "")

# --- CodeExplorer ----------------------------------------------------------
GITHUB_ACCESS_TOKEN = getenv("GITHUB_ACCESS_TOKEN", "")
REPOS_DIR = Path(getenv("REPOS_DIR", ".scout/repos"))

# --- S3Source (compile-only) -----------------------------------------------
AWS_ACCESS_KEY_ID = getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = getenv("AWS_REGION", "")

# --- Runtime objects (DB-dependent) ----------------------------------------
agent_db = get_postgres_db()
scout_knowledge = create_knowledge("Scout Knowledge", "scout_knowledge")
scout_learnings = create_knowledge("Scout Learnings", "scout_learnings")
