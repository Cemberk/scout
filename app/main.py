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
from scout.agents import compiler, navigator, researcher
from scout.agents.settings import scout_knowledge, scout_learnings
from scout.config import SLACK_SIGNING_SECRET, SLACK_TOKEN
from scout.team import scout

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "prd")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Interfaces — Slack
# ---------------------------------------------------------------------------
# Channel scoping is configured via the Slack app (install to channels).
# No server-side allowlist middleware.
interfaces: list = []
if SLACK_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    # agno's Slack interface reads SLACK_TOKEN / SLACK_SIGNING_SECRET from
    # env directly. Pass-through kwargs the current Slack class accepts:
    # agent / team / workflow / prefix / tags / reply_to_mentions_only.
    interfaces.append(Slack(team=scout, reply_to_mentions_only=False))


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    _run_migrations()
    _build_initial_manifest()
    _register_schedules()
    yield


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agents: list = [a for a in [navigator, researcher, compiler] if a is not None]

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
# Startup helpers
# ---------------------------------------------------------------------------
def _run_migrations() -> None:
    try:
        from db.migrations import run_migrations

        run_migrations()
        print("[scout] Migrations: applied")
    except Exception as e:
        print(f"[scout] Migrations: failed: {e}")


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

    # Every 10 min: hits /compile/run directly (no team round-trip). The
    # Compiler runs lint checks as part of each full compile pass, so there
    # is no separate wiki-lint schedule.
    mgr.create(
        name="wiki-compile",
        cron="*/10 * * * *",
        endpoint="/compile/run",
        payload={"force": False},
        timezone="UTC",
        description="Iterate compile-on sources every 10 minutes (includes lint pass)",
        if_exists="update",
    )

    # Source health refresh.
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
                "It's Friday — time for a weekly review. Summarize this "
                "week's conversations, decisions, and open action items. "
                "Cite any compiled wiki articles you reference." + slack_post
            ),
        },
        timezone="America/New_York",
        description="Friday afternoon weekly review draft",
        if_exists="update",
    )


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
