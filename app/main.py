"""
Scout AgentOS
=============

The main entry point for Scout.

Run:
    python -m app.main
"""

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from agno.os import AgentOS

from app.router import create_router
from db import get_postgres_db
from scout.agents import code_explorer, compiler, doctor, engineer, navigator
from scout.settings import (
    SLACK_BOT_TOKEN,
    SLACK_SIGNING_SECRET,
    scout_knowledge,
    scout_learnings,
)
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
if SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    # Pass token + signing_secret to Agno's Slack interface.
    interfaces.append(
        Slack(
            team=scout,
            token=SLACK_BOT_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            reply_to_mentions_only=False,
        )
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    _create_tables()
    _build_initial_manifest()
    _register_schedules()
    _kick_initial_compile()
    yield


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agents: list = [navigator, compiler, code_explorer, engineer, doctor]

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
def _create_tables() -> None:
    try:
        from db.tables import create_tables

        create_tables()
        print("[scout] Tables: applied")
    except Exception as e:
        print(f"[scout] Tables: failed: {e}")


def _build_initial_manifest() -> None:
    try:
        from scout.manifest import reload_manifest

        m = reload_manifest()
        print(f"[scout] Manifest: {len(m.sources)} source(s)")
    except Exception as e:
        print(f"[scout] Manifest build failed: {e}")


def _kick_initial_compile() -> None:
    """Fire a one-shot compile in a background thread at startup.

    The hourly `wiki-compile` cron only runs on the hour, so a user who
    does `docker compose up` at 10:05 would otherwise wait until 11:00
    for the first wiki to appear. We run one compile pass immediately
    in a daemon thread so the wiki is populated within ~30 seconds of
    boot.

    Daemon thread so a slow compile doesn't block shutdown. We swallow
    exceptions; if OPENAI_API_KEY is bad, the hourly cron surfaces the
    failure on its own schedule.
    """
    import threading

    def _run() -> None:
        try:
            from scout.compile import compile_all
            from scout.settings import scout_knowledge

            results = compile_all(knowledge=scout_knowledge)
            counts = {sid: len(r) for sid, r in results.items()}
            print(f"[scout] Initial compile: {counts}")
        except Exception as e:
            print(f"[scout] Initial compile failed: {e}")

    threading.Thread(target=_run, name="scout-initial-compile", daemon=True).start()


def _register_schedules() -> None:
    """Register Scout's scheduled tasks (idempotent on every startup)."""
    from agno.scheduler import ScheduleManager

    mgr = ScheduleManager(get_postgres_db())
    mgr.create(
        name="wiki-compile",
        cron="0 * * * *",
        endpoint="/compile/run",
        payload={"force": False},
        timezone="UTC",
        description="Iterate compile-on sources every hour (includes lint pass)",
        if_exists="update",
    )


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
