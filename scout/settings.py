"""
Scout Settings
==============

Environment-derived constants, repo paths, and DB-dependent runtime
objects used across Scout. DB objects are created at import time so
every agent shares the same instance.

Feature/source-enablement is derived at call sites from the env vars
below — no pre-computed ``*_ENABLED`` flags.
"""

from os import getenv
from pathlib import Path

from db import create_knowledge, get_postgres_db

# --- Paths ----------------------------------------------------------------
# context/compiled/ is gone — the active WikiContext's backend is the
# source of truth for compiled articles now (LocalBackend root is
# configured via SCOUT_WIKI, default local:./context).
_REPO_ROOT = Path(__file__).parent.parent
CONTEXT_DIR = _REPO_ROOT / "context"
CONTEXT_RAW_DIR = CONTEXT_DIR / "raw"
CONTEXT_VOICE_DIR = CONTEXT_DIR / "voice"
DOCS_DIR = _REPO_ROOT / "docs"

# --- Web research: Parallel (premium) or keyless Exa MCP fallback ----------
PARALLEL_API_KEY = getenv("PARALLEL_API_KEY", "")
EXA_API_KEY = getenv("EXA_API_KEY", "")
EXA_MCP_URL = (
    f"https://mcp.exa.ai/mcp?exaApiKey={EXA_API_KEY}&tools=web_search_exa,web_fetch_exa"
    if EXA_API_KEY
    else "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
)

# --- Slack (Scout's own bot identity) --------------------------------------
SLACK_BOT_TOKEN = getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")

# --- Outbound send gate ----------------------------------------------------
# When false (default), Gmail and Calendar tools exclude their send /
# create / update / delete functions — the Leader can draft but not
# actually send. Slack is always opt-in via SLACK_BOT_TOKEN.
SCOUT_ALLOW_SENDS = getenv("SCOUT_ALLOW_SENDS", "").lower() in ("true", "1", "yes")

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
# scout_knowledge is gone per §7.2 — routing content folds into
# scout_learnings (one operational-memory store, shared by Explorer /
# Engineer / Doctor).
agent_db = get_postgres_db()
scout_learnings = create_knowledge("Scout Learnings", "scout_learnings")
