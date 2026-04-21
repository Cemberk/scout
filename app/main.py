"""
Scout AgentOS
================
"""

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from agno.os import AgentOS

from app.router import create_router
from db import get_postgres_db
from scout.agents.doctor import doctor
from scout.agents.engineer import engineer
from scout.agents.explorer import explorer
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
interfaces: list = []
if SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    interfaces.append(
        Slack(
            team=scout,
            token=SLACK_BOT_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            loading_messages=["Thinking...", "Working...", "Simmering..."],
            reply_to_mentions_only=True,
        )
    )


# ---------------------------------------------------------------------------
# Lifespan — Create tables, wire up wiki
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    _create_tables()
    _build_wiki_and_contexts()
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
        print("[scout] Tables: created")
    except Exception as e:
        print(f"[scout] Tables: failed: {e}")


def _build_wiki_and_contexts() -> None:
    """Build the wiki + contexts from env and publish via ``set_runtime``.

    ``set_runtime`` installs the registry singletons and rewires
    Explorer + Engineer tool lists in one call. Failures are logged but
    don't block startup — agents can still chat even if a context is
    misconfigured; Doctor surfaces the issue.
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
