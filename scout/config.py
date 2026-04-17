from os import getenv
from pathlib import Path

from scout.paths import (
    CONTEXT_COMPILED_DIR,
    CONTEXT_DIR,
    CONTEXT_RAW_DIR,
    CONTEXT_VOICE_DIR,
    DOCUMENTS_DIR,
)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
EXA_API_KEY = getenv("EXA_API_KEY", "")
PARALLEL_API_KEY = getenv("PARALLEL_API_KEY", "")

SLACK_TOKEN = getenv("SLACK_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")
# Comma-separated channel IDs Scout is allowed to post to (empty = allow all)
SLACK_CHANNEL_ALLOWLIST = tuple(
    c.strip() for c in getenv("SLACK_CHANNEL_ALLOWLIST", "").split(",") if c.strip()
)
# SlackSource is live-read only. Needs a token; allowlist is optional.
SLACK_SOURCE_ENABLED = bool(SLACK_TOKEN)

GOOGLE_CLIENT_ID = getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_PROJECT_ID = getenv("GOOGLE_PROJECT_ID", "")
GOOGLE_INTEGRATION_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_PROJECT_ID)

# Drive folder IDs (comma-separated). When set + Google enabled, GoogleDriveSource is registered.
GOOGLE_DRIVE_FOLDER_IDS = tuple(
    f.strip() for f in getenv("GOOGLE_DRIVE_FOLDER_IDS", "").split(",") if f.strip()
)
DRIVE_SOURCE_ENABLED = GOOGLE_INTEGRATION_ENABLED and bool(GOOGLE_DRIVE_FOLDER_IDS)

SCOUT_CONTEXT_DIR = Path(getenv("SCOUT_CONTEXT_DIR", str(CONTEXT_DIR)))
SCOUT_RAW_DIR = Path(getenv("SCOUT_RAW_DIR", str(SCOUT_CONTEXT_DIR / "raw")))
SCOUT_COMPILED_DIR = Path(getenv("SCOUT_COMPILED_DIR", str(SCOUT_CONTEXT_DIR / "compiled")))
SCOUT_VOICE_DIR = Path(getenv("SCOUT_VOICE_DIR", str(SCOUT_CONTEXT_DIR / "voice")))

# Workspace scoping — fixed for Phase 1, real multi-workspace lands in Phase 4
WORKSPACE_ID = getenv("SCOUT_WORKSPACE_ID", "default")

EXA_MCP_URL = (
    f"https://mcp.exa.ai/mcp?exaApiKey={EXA_API_KEY}&tools=web_search_exa"
    if EXA_API_KEY
    else "https://mcp.exa.ai/mcp?tools=web_search_exa"
)

# Git sync — push context/ to GitHub, pull on startup
GITHUB_ACCESS_TOKEN = getenv("GITHUB_ACCESS_TOKEN", "")
SCOUT_REPO_URL = getenv("SCOUT_REPO_URL", "")
GIT_SYNC_ENABLED = bool(GITHUB_ACCESS_TOKEN and SCOUT_REPO_URL)

# GitHubSource — live-read over locally cloned repos + ad-hoc search_code.
# GITHUB_ACCESS_TOKEN is Scout's own context repo token (not this one).
GITHUB_READ_TOKEN = getenv("GITHUB_READ_TOKEN", "")
GITHUB_REPOS = tuple(
    r.strip() for r in getenv("GITHUB_REPOS", "").split(",") if r.strip()
)
GITHUB_SOURCE_ENABLED = bool(GITHUB_REPOS and GITHUB_READ_TOKEN)

# S3Source — compile-only in this build. S3_BUCKETS entries are
# `bucket[:prefix]`. One Source instance is registered per entry.
AWS_ACCESS_KEY_ID = getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = getenv("AWS_REGION", "")
S3_BUCKETS = tuple(
    b.strip() for b in getenv("S3_BUCKETS", "").split(",") if b.strip()
)
S3_SOURCE_ENABLED = bool(
    S3_BUCKETS and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_REGION
)


# Re-export for convenience
__all__ = [
    "AWS_ACCESS_KEY_ID",
    "AWS_REGION",
    "AWS_SECRET_ACCESS_KEY",
    "CONTEXT_COMPILED_DIR",
    "CONTEXT_DIR",
    "CONTEXT_RAW_DIR",
    "CONTEXT_VOICE_DIR",
    "DOCUMENTS_DIR",
    "DRIVE_SOURCE_ENABLED",
    "EXA_API_KEY",
    "EXA_MCP_URL",
    "GIT_SYNC_ENABLED",
    "GITHUB_ACCESS_TOKEN",
    "GITHUB_READ_TOKEN",
    "GITHUB_REPOS",
    "GITHUB_SOURCE_ENABLED",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_DRIVE_FOLDER_IDS",
    "GOOGLE_INTEGRATION_ENABLED",
    "GOOGLE_PROJECT_ID",
    "PARALLEL_API_KEY",
    "S3_BUCKETS",
    "S3_SOURCE_ENABLED",
    "SCOUT_COMPILED_DIR",
    "SCOUT_CONTEXT_DIR",
    "SCOUT_RAW_DIR",
    "SCOUT_REPO_URL",
    "SCOUT_VOICE_DIR",
    "SLACK_CHANNEL_ALLOWLIST",
    "SLACK_SIGNING_SECRET",
    "SLACK_SOURCE_ENABLED",
    "SLACK_TOKEN",
    "WORKSPACE_ID",
]
