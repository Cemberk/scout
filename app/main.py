"""
AgentOS Entrypoint
==================
"""

import asyncio
from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from agno.os import AgentOS
from agno.utils.log import log_warning

from app.router import create_router
from db import get_postgres_db
from scout.contexts import create_context_providers, get_context_providers
from scout.team import scout

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "prd")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Interfaces — Slack lights up when both env vars are set
# ---------------------------------------------------------------------------
SLACK_BOT_TOKEN = getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")

interfaces: list = []
if SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    interfaces.append(
        Slack(
            agent=scout,
            streaming=True,
            token=SLACK_BOT_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            resolve_user_identity=True,
        )
    )


# ---------------------------------------------------------------------------
# Lifespan — Create tables and wire up contexts
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    from db.tables import create_tables

    create_tables()
    create_context_providers()
    try:
        yield
    finally:
        # Providers that hold resources (MCP sessions, watch streams)
        # override `aclose()`; the base class default is a no-op.
        # `return_exceptions=True` so one stuck teardown can't block
        # others on the way down.
        providers = list(get_context_providers())
        if providers:
            results = await asyncio.gather(
                *(p.aclose() for p in providers),
                return_exceptions=True,
            )
            for provider, outcome in zip(providers, results, strict=True):
                if isinstance(outcome, BaseException):
                    log_warning(
                        f"context {provider.id!r} aclose raised "
                        f"{type(outcome).__name__}: {outcome}"
                    )


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
    agents=[scout],
    interfaces=interfaces,
    config=str(Path(__file__).parent / "config.yaml"),
)

app = agent_os.get_app()
app.include_router(create_router(agent_os.settings))


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
