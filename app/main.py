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
from scout.contexts import build_contexts, set_runtime
from scout.settings import scout_learnings
from scout.team import scout

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
    _wire_contexts()
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
    agents=[explorer, engineer, doctor],
    knowledge=[scout_learnings],
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


def _wire_contexts() -> None:
    """Build the contexts from env and publish via ``set_runtime``."""
    try:
        contexts = build_contexts()
        set_runtime(contexts)
        print(f"[scout] Contexts: {[c.id for c in contexts]}")
    except Exception as e:
        print(f"[scout] Contexts wiring failed: {e}")


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
