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

# Compile model — same as agents in Phase 1; can be split later
COMPILE_MODEL_ID = getenv("SCOUT_COMPILE_MODEL", "gpt-5.4")

# Re-export for convenience
__all__ = [
    "CONTEXT_COMPILED_DIR",
    "CONTEXT_DIR",
    "CONTEXT_RAW_DIR",
    "CONTEXT_VOICE_DIR",
    "COMPILE_MODEL_ID",
    "DOCUMENTS_DIR",
    "DRIVE_SOURCE_ENABLED",
    "EXA_API_KEY",
    "EXA_MCP_URL",
    "GIT_SYNC_ENABLED",
    "GITHUB_ACCESS_TOKEN",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_DRIVE_FOLDER_IDS",
    "GOOGLE_INTEGRATION_ENABLED",
    "GOOGLE_PROJECT_ID",
    "PARALLEL_API_KEY",
    "SCOUT_COMPILED_DIR",
    "SCOUT_CONTEXT_DIR",
    "SCOUT_RAW_DIR",
    "SCOUT_REPO_URL",
    "SCOUT_VOICE_DIR",
    "SLACK_CHANNEL_ALLOWLIST",
    "SLACK_SIGNING_SECRET",
    "SLACK_TOKEN",
    "WORKSPACE_ID",
]
