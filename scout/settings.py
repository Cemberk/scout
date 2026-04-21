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
# The active ``WikiContextProvider``'s backend owns raw/ + compiled/ +
# .scout/state.json. These repo-level paths only expose the voice guides
# the Leader reads before drafting.
_REPO_ROOT = Path(__file__).parent.parent
CONTEXT_DIR = _REPO_ROOT / "context"
CONTEXT_VOICE_DIR = CONTEXT_DIR / "voice"
DOCS_DIR = _REPO_ROOT / "docs"

# --- Web research: Parallel (premium) or keyless Exa MCP fallback ----------
# The web provider is built in scout/context/config.py::_build_default_web —
# these vars are read from os.getenv inside the backend constructors, but we
# keep them exposed here so other consumers (ingest, health) can reach them.
PARALLEL_API_KEY = getenv("PARALLEL_API_KEY", "")
EXA_API_KEY = getenv("EXA_API_KEY", "")

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

# --- GitHub (GithubContextProvider + GithubWikiBackend) --------------------
GITHUB_ACCESS_TOKEN = getenv("GITHUB_ACCESS_TOKEN", "")
REPOS_DIR = Path(getenv("REPOS_DIR", ".scout/repos"))

# --- AWS (S3ContextProvider + S3WikiBackend) --------------------------------
AWS_ACCESS_KEY_ID = getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = getenv("AWS_REGION", "")

# --- Runtime objects (DB-dependent) ----------------------------------------
# One shared operational-memory store: routing hints, corrections, and
# per-user preferences land here. Explorer / Engineer / Doctor all
# attach it as their LearningMachine's knowledge base in agentic mode.
agent_db = get_postgres_db()
scout_learnings = create_knowledge("Scout Learnings", "scout_learnings")
