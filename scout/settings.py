"""
Scout Settings
==============

Single consolidated home for:

1. Environment-derived constants (loaded at import, no DB required).
2. Derived feature flags (which sources are enabled given the env).
3. Runtime objects that depend on the DB (``agent_db``, the Knowledge
   bases). These are created at module load so every agent that imports
   ``scout.settings`` shares the same instance.
"""

import os
from os import getenv
from pathlib import Path

from db import create_knowledge, get_postgres_db
from scout.paths import (
    CONTEXT_COMPILED_DIR,
    CONTEXT_DIR,
    CONTEXT_RAW_DIR,
    CONTEXT_VOICE_DIR,
)

# ---------------------------------------------------------------------------
# 1. Environment
# ---------------------------------------------------------------------------

# --- Web research: Parallel (premium) or keyless Exa MCP fallback ----------
# One is always present — Navigator always has a web-search backend.
PARALLEL_API_KEY = getenv("PARALLEL_API_KEY", "")
EXA_API_KEY = getenv("EXA_API_KEY", "")
EXA_MCP_URL = (
    f"https://mcp.exa.ai/mcp?exaApiKey={EXA_API_KEY}&tools=web_search_exa,web_fetch_exa"
    if EXA_API_KEY
    else "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
)

# --- Slack (Scout's own bot identity) --------------------------------------
# Scout runs as its own Slack bot. SLACK_BOT_TOKEN is the xoxb- token from
# the Slack app install. Channel scope is controlled by which channels the
# bot is invited into — there's no server-side allowlist.
SLACK_BOT_TOKEN = getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")
# Agno's SlackTools / Slack interface read SLACK_TOKEN from env directly.
# Mirror SLACK_BOT_TOKEN into SLACK_TOKEN so those integrations continue to
# work without the caller having to set both.
if SLACK_BOT_TOKEN:
    os.environ.setdefault("SLACK_TOKEN", SLACK_BOT_TOKEN)

# --- Google (Gmail + Calendar + Drive) -------------------------------------
# One Google app, one set of creds, used by Scout for Gmail, Calendar, and
# Drive. Drive scope is managed on the Google side by sharing folders with
# Scout's account — we no longer take a folder-ID allowlist.
GOOGLE_CLIENT_ID = getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_PROJECT_ID = getenv("GOOGLE_PROJECT_ID", "")

# --- CodeExplorer ---------------------------------------------------------
# Public repos clone tokenless; set this for private repos or to raise the
# API rate ceiling.
GITHUB_ACCESS_TOKEN = getenv("GITHUB_ACCESS_TOKEN", "")
# Clone cache. In docker-compose this points at the ``repos`` named volume
# (/repos); outside Docker it falls back to a local gitignored path.
REPOS_DIR = Path(getenv("REPOS_DIR", ".scout/repos"))

# --- S3Source (compile-only) ----------------------------------------------
# S3_BUCKETS entries are ``bucket[:prefix]``; one Source is registered per entry.
AWS_ACCESS_KEY_ID = getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = getenv("AWS_REGION", "")
S3_BUCKETS = tuple(b.strip() for b in getenv("S3_BUCKETS", "").split(",") if b.strip())

# --- Context directories --------------------------------------------------
SCOUT_CONTEXT_DIR = Path(getenv("SCOUT_CONTEXT_DIR", str(CONTEXT_DIR)))
SCOUT_RAW_DIR = Path(getenv("SCOUT_RAW_DIR", str(SCOUT_CONTEXT_DIR / "raw")))
SCOUT_COMPILED_DIR = Path(getenv("SCOUT_COMPILED_DIR", str(SCOUT_CONTEXT_DIR / "compiled")))
SCOUT_VOICE_DIR = Path(getenv("SCOUT_VOICE_DIR", str(SCOUT_CONTEXT_DIR / "voice")))

# --- Send gating ----------------------------------------------------------
# Gates Leader outbound actions (Gmail send, Calendar write, Slack post).
# When false (the default), those tools are wired as drafts-only.
SCOUT_ALLOW_SENDS = getenv("SCOUT_ALLOW_SENDS", "false").strip().lower() in ("1", "true", "yes", "on")

# ---------------------------------------------------------------------------
# 2. Derived feature flags
# ---------------------------------------------------------------------------
GOOGLE_INTEGRATION_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_PROJECT_ID)
# Drive piggybacks on Google integration — no separate folder allowlist.
# Scope is managed on the Google side (share folders with Scout's account).
DRIVE_SOURCE_ENABLED = GOOGLE_INTEGRATION_ENABLED
# SlackSource is live-read only. Channel scope is configured via the
# Slack app (install to channels) — no server-side allowlist.
SLACK_SOURCE_ENABLED = bool(SLACK_BOT_TOKEN)
S3_SOURCE_ENABLED = bool(S3_BUCKETS and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_REGION)

# ---------------------------------------------------------------------------
# 3. Runtime objects (DB-dependent)
# ---------------------------------------------------------------------------
agent_db = get_postgres_db()
scout_knowledge = create_knowledge("Scout Knowledge", "scout_knowledge")
scout_learnings = create_knowledge("Scout Learnings", "scout_learnings")


__all__ = [
    # Paths re-exports
    "CONTEXT_COMPILED_DIR",
    "CONTEXT_DIR",
    "CONTEXT_RAW_DIR",
    "CONTEXT_VOICE_DIR",
    # AWS / S3
    "AWS_ACCESS_KEY_ID",
    "AWS_REGION",
    "AWS_SECRET_ACCESS_KEY",
    "S3_BUCKETS",
    "S3_SOURCE_ENABLED",
    # Web
    "EXA_API_KEY",
    "EXA_MCP_URL",
    "PARALLEL_API_KEY",
    # Slack
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "SLACK_SOURCE_ENABLED",
    # Google
    "DRIVE_SOURCE_ENABLED",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_INTEGRATION_ENABLED",
    "GOOGLE_PROJECT_ID",
    # CodeExplorer
    "GITHUB_ACCESS_TOKEN",
    "REPOS_DIR",
    # Context dirs
    "SCOUT_COMPILED_DIR",
    "SCOUT_CONTEXT_DIR",
    "SCOUT_RAW_DIR",
    "SCOUT_VOICE_DIR",
    # Send gating
    "SCOUT_ALLOW_SENDS",
    # Runtime objects
    "agent_db",
    "scout_knowledge",
    "scout_learnings",
]
