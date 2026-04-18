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
    _kick_initial_compile()
    yield


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agents: list = [navigator, researcher, compiler]

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
# Empty-prompt middleware
# ---------------------------------------------------------------------------
# AgentOS's /teams/*/runs form validator rejects empty `message` as missing.
# We want the Leader to respond to an empty prompt gracefully (asking for
# clarification) rather than surfacing a 422. This middleware rewrites the
# form body so the validator sees a non-empty placeholder.


@app.middleware("http")
async def _rewrite_empty_prompt(request, call_next):  # type: ignore[no-untyped-def]
    path = request.url.path
    if request.method == "POST" and path.endswith("/runs") and "/teams/" in path:
        ctype = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in ctype:
            body = await request.body()
            form_text = body.decode("utf-8", errors="ignore")
            from urllib.parse import parse_qsl, urlencode

            pairs = parse_qsl(form_text, keep_blank_values=True)
            msg = next((v for k, v in pairs if k == "message"), None)
            if not msg or not msg.strip():
                placeholder = "(the user submitted an empty prompt — ask them what they need)"
                pairs = [(k, v) for k, v in pairs if k != "message"]
                pairs.append(("message", placeholder))
                new_body = urlencode(pairs).encode("utf-8")

                # Rebuild scope with corrected content-length and inject receive.
                async def _receive():  # type: ignore[no-untyped-def]
                    return {"type": "http.request", "body": new_body, "more_body": False}

                new_headers = [(k, v) for k, v in request.scope.get("headers", []) if k.lower() != b"content-length"]
                new_headers.append((b"content-length", str(len(new_body)).encode()))
                new_scope = dict(request.scope)
                new_scope["headers"] = new_headers
                from starlette.requests import Request as StarletteRequest

                new_request = StarletteRequest(new_scope, _receive)
                # call_next respects Request object, not the passed-in one, so
                # we build our own mini-ASGI cycle by re-dispatching via app.
                # Simpler: monkey-patch the existing request.
                request._body = new_body  # type: ignore[attr-defined]
                request._receive = _receive  # type: ignore[attr-defined]
                request.scope["headers"] = new_headers
                # Also clear any cached form state.
                if hasattr(request, "_form"):
                    delattr(request, "_form")
                del new_request  # unused
    return await call_next(request)


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


def _kick_initial_compile() -> None:
    """Fire a one-shot compile in a background thread at startup.

    The hourly `wiki-compile` cron only runs on the hour, so a user who
    does `docker compose up` at 10:05 would otherwise wait until 11:00
    for the first wiki to appear. We run one compile pass immediately
    in a daemon thread so the wiki is populated within ~30 seconds of
    boot — Demo 3 ("give Scout your context") then works without
    anyone having to run `docker exec ... compile` by hand.

    Daemon thread so a slow compile doesn't block shutdown. We swallow
    exceptions; if OPENAI_API_KEY is bad, the hourly cron surfaces the
    failure on its own schedule.
    """
    import threading

    def _run() -> None:
        try:
            from scout.agents.settings import scout_knowledge
            from scout.compile import compile_all

            results = compile_all(knowledge=scout_knowledge)
            counts = {sid: len(r) for sid, r in results.items()}
            print(f"[scout] Initial compile: {counts}")
        except Exception as e:
            print(f"[scout] Initial compile failed: {e}")

    threading.Thread(target=_run, name="scout-initial-compile", daemon=True).start()


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

    # Hourly: hits /compile/run directly (no team round-trip). The
    # Compiler runs lint checks as part of each full compile pass, so there
    # is no separate wiki-lint schedule. Users can always run
    # `docker exec -it scout-api python -m scout compile` for an
    # immediate recompile.
    mgr.create(
        name="wiki-compile",
        cron="0 * * * *",
        endpoint="/compile/run",
        payload={"force": False},
        timezone="UTC",
        description="Iterate compile-on sources every hour (includes lint pass)",
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
