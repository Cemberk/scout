"""
Scout AgentOS
=============

The main entry point for Scout v3.

Run:
    python -m app.main
"""

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from agno.os import AgentOS

from app.router import create_router
from db import get_postgres_db
from scout.agents import compiler, linter, navigator, researcher, syncer
from scout.agents.settings import scout_knowledge, scout_learnings
from scout.config import GIT_SYNC_ENABLED, SCOUT_REPO_URL, SLACK_SIGNING_SECRET, SLACK_TOKEN
from scout.team import scout

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "prd")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Interfaces — Slack with channel allowlist enforcement
# ---------------------------------------------------------------------------
interfaces: list = []
if SLACK_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    interfaces.append(
        Slack(
            team=scout,
            streaming=True,
            token=SLACK_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            resolve_user_identity=True,
        )
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    _run_migrations()
    _init_git_sync()
    _build_initial_manifest()
    _register_schedules()
    yield


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agents: list = [a for a in [navigator, researcher, compiler, linter, syncer] if a is not None]

agent_os = AgentOS(
    name="Scout",
    tracing=True,
    scheduler=True,
    scheduler_base_url=scheduler_base_url,
    authorization=runtime_env == "prd",
    lifespan=lifespan,
    db=get_postgres_db(),
    teams=[scout],
    agents=agents,
    knowledge=[scout_knowledge, scout_learnings],
    interfaces=interfaces,
    config=str(Path(__file__).parent / "config.yaml"),
)

app = agent_os.get_app()
app.include_router(create_router(agent_os.settings))


# ---------------------------------------------------------------------------
# Slack channel allowlist middleware (defense in depth)
# ---------------------------------------------------------------------------
def _install_slack_allowlist() -> None:
    """If SLACK_CHANNEL_ALLOWLIST is set, drop /slack events from other channels.

    The agno SlackTools enforces the allowlist on outbound posts; this
    middleware enforces it on inbound events too, so messages in other
    channels never even reach the team.
    """
    from scout.config import SLACK_CHANNEL_ALLOWLIST

    if not SLACK_CHANNEL_ALLOWLIST:
        return

    from starlette.requests import Request
    from starlette.responses import Response

    @app.middleware("http")
    async def slack_allowlist(request: Request, call_next):  # type: ignore[no-untyped-def]
        if not request.url.path.startswith("/slack"):
            return await call_next(request)
        body = await request.body()
        # Reconstruct the request so downstream handlers can read body.
        async def _receive():
            return {"type": "http.request", "body": body, "more_body": False}
        request._receive = _receive  # type: ignore[attr-defined]

        try:
            import json as _json

            payload = _json.loads(body or b"{}")
        except Exception:
            return await call_next(request)

        channel = (
            payload.get("event", {}).get("channel")
            or payload.get("channel_id")
            or payload.get("channel")
        )
        if channel and channel not in SLACK_CHANNEL_ALLOWLIST:
            return Response(status_code=200)  # ack, ignore
        return await call_next(request)


_install_slack_allowlist()


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------
def _run_migrations() -> None:
    try:
        from db.migrations import run_migrations

        run_migrations()
        print("[scout] Migrations: applied")
    except Exception as e:
        print(f"[scout] Migrations: failed: {e}")


def _init_git_sync() -> None:
    """Initialize context/ as a git repo and pull latest from GitHub."""
    if not GIT_SYNC_ENABLED:
        return
    from scout.tools.git import init_context_repo

    result = init_context_repo(SCOUT_REPO_URL)
    print(f"[scout] Git sync: {result}")


def _build_initial_manifest() -> None:
    try:
        from scout.manifest import reload_manifest

        m = reload_manifest()
        print(f"[scout] Manifest: {len(m.sources)} source(s)")
    except Exception as e:
        print(f"[scout] Manifest build failed: {e}")


def _register_schedules() -> None:
    """Register all scheduled tasks (idempotent — safe to run on every startup)."""
    from agno.scheduler import ScheduleManager

    mgr = ScheduleManager(get_postgres_db())
    slack_post = "\n\nWhen done, post the results to the #scout-updates Slack channel." if SLACK_TOKEN else ""

    mgr.create(
        name="context-refresh",
        cron="0 8 * * *",
        endpoint="/context/reload",
        payload={},
        timezone="America/New_York",
        description="Daily context file re-index",
        if_exists="update",
    )

    mgr.create(
        name="daily-briefing",
        cron="0 8 * * 1-5",
        endpoint="/teams/scout/runs",
        payload={
            "message": (
                "Good morning. Give me a quick briefing to start the day:\n"
                "1. Check today's calendar — list events with times, flag any that need prep.\n"
                "2. Summarize unread or flagged emails (if Gmail is enabled).\n"
                "3. List open priorities and action items from recent conversations.\n"
                "Keep it short — a morning scan, not a full report." + slack_post
            ),
        },
        timezone="America/New_York",
        description="Weekday morning briefing — calendar, emails, priorities",
        if_exists="update",
    )

    # v3 change: every 10 minutes, hits /compile/run directly (no team round-trip).
    mgr.create(
        name="wiki-compile",
        cron="*/10 * * * *",
        endpoint="/compile/run",
        payload={"force": False},
        timezone="UTC",
        description="Iterate compile-on sources every 10 minutes",
        if_exists="update",
    )

    # v3 NEW: source health refresh.
    mgr.create(
        name="source-health-check",
        cron="*/15 * * * *",
        endpoint="/manifest/reload",
        payload={},
        timezone="UTC",
        description="Refresh manifest by health-checking every source",
        if_exists="update",
    )

    mgr.create(
        name="inbox-digest",
        cron="0 12 * * 1-5",
        endpoint="/teams/scout/runs",
        payload={
            "message": (
                "Midday inbox digest:\n"
                "1. Summarize emails from this morning — group by sender or thread.\n"
                "2. Flag anything that needs a response today.\n"
                "3. Note any action items with owners and deadlines." + slack_post
            ),
        },
        timezone="America/New_York",
        description="Weekday midday email digest (requires Gmail)",
        if_exists="update",
    )

    mgr.create(
        name="learning-summary",
        cron="0 10 * * 1",
        endpoint="/teams/scout/runs",
        payload={
            "message": (
                "Monday learning check-in:\n"
                "1. Query what you've learned recently from scout_learnings.\n"
                "2. Summarize patterns, preferences, and insights you've picked up.\n"
                "3. Note anything that seems wrong or worth revisiting." + slack_post
            ),
        },
        timezone="America/New_York",
        description="Monday morning learning system summary",
        if_exists="update",
    )

    mgr.create(
        name="weekly-review",
        cron="0 17 * * 5",
        endpoint="/teams/scout/runs",
        payload={
            "message": (
                "It's Friday — time for a weekly review.\n"
                "1. Read context/templates/weekly-review.md for the structure.\n"
                "2. Fill it in based on this week's conversations, decisions, and action items.\n"
                "3. Save the draft to context/meetings/ using the filename format "
                "YYYY-MM-DD - weekly-review.md (use today's date)." + slack_post
            ),
        },
        timezone="America/New_York",
        description="Friday afternoon weekly review draft",
        if_exists="update",
    )

    mgr.create(
        name="wiki-lint",
        cron="0 8 * * 0",
        endpoint="/wiki/lint",
        payload={},
        timezone="America/New_York",
        description="Weekly wiki health check (compile conflicts, stale articles, source flap)",
        if_exists="update",
    )

    if GIT_SYNC_ENABLED:
        mgr.create(
            name="sync-pull",
            cron="*/30 * * * *",
            endpoint="/sync/pull",
            payload={},
            timezone="UTC",
            description="Pull remote context/ changes from GitHub every 30 minutes",
            if_exists="update",
        )


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
