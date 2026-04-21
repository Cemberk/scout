"""
AgentOS Entrypoint
==================
"""

import logging
from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from agno.os import AgentOS

from app.router import create_router
from db import get_postgres_db
from scout.agents.engineer import engineer
from scout.agents.explorer import explorer
from scout.contexts import build_contexts
from scout.team import scout

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "prd")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Lifespan — Create tables and wire up contexts
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    _create_tables()
    _create_contexts()
    yield


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agent_os = AgentOS(
    name="Scout",
    tracing=True,
    scheduler=True,
    scheduler_base_url=scheduler_base_url,
    authorization=runtime_env == "prd",
    lifespan=lifespan,
    db=get_postgres_db(),
    teams=[scout],
    agents=[explorer, engineer],
    config=str(Path(__file__).parent / "config.yaml"),
)

app = agent_os.get_app()
app.include_router(create_router(agent_os.settings))


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------
def _create_tables() -> None:
    from db.tables import create_tables

    create_tables()
    log.info("Tables: created")


def _create_contexts() -> None:
    """Build the contexts from env and cache them for the process."""
    contexts = build_contexts()
    log.info("Contexts: %s", [c.id for c in contexts])


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
