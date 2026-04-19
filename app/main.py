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
from scout.agents import doctor, engineer, explorer
from scout.context.config import build_contexts, build_wiki
from scout.settings import (
    SLACK_BOT_TOKEN,
    SLACK_SIGNING_SECRET,
    scout_learnings,
)
from scout.team import scout
from scout.tools.ask_context import set_runtime

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

    interfaces.append(
        Slack(
            team=scout,
            token=SLACK_BOT_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            reply_to_mentions_only=False,
        )
    )


# ---------------------------------------------------------------------------
# Lifespan — tables + wiki/contexts wire-up
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    _create_tables()
    _wire_wiki_and_contexts()
    yield


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agents: list = [explorer, engineer, doctor]

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
    knowledge=[scout_learnings],
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


def _wire_wiki_and_contexts() -> None:
    """Build the WikiContext + Context list from env and publish them
    via ``scout.tools.ask_context.set_runtime`` so the Explorer /
    Engineer / Doctor tools can resolve the active instances.

    Failures are logged but don't block startup — agents can still chat
    even if a context is misconfigured; Doctor surfaces the issue.
    """
    try:
        wiki = build_wiki()
        contexts = build_contexts()
        set_runtime(wiki, contexts)
        print(f"[scout] Wiki: {wiki.id}; Contexts: {[c.id for c in contexts]}")
    except Exception as e:
        print(f"[scout] Wiki/contexts wiring failed: {e}")


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
