"""Diagnostic tools for the Doctor agent (§7.1).

Doctor surface:
- ``health(target_id)``  — one target, 'wiki' or a context id.
- ``health_all()``       — wiki + every registered context.
- ``db_health()``        — Postgres connectivity + table existence.
- ``env_report()``       — env var presence (redacted, grouped by integration).

The old manifest / compile / repo-cache tools are gone — the manifest
itself is gone (§7.2), compile lives inside WikiContext, and the repo
cache goes with the CodeExplorer agent.
"""

from __future__ import annotations

import json
import logging

from agno.tools import tool

log = logging.getLogger(__name__)


# Expected environment variables, grouped by integration. Values are
# descriptions shown back to the user, not live env reads.
_EXPECTED_ENV: dict[str, dict[str, str]] = {
    "core": {
        "OPENAI_API_KEY": "GPT-5.4 for every agent + embeddings",
        "SCOUT_WIKI": "Wiki backend spec (default local:./context). Examples: github:owner/repo, s3:bucket/prefix",
        "SCOUT_CONTEXTS": "Comma-separated live-read context specs (slack,gmail,drive,github:owner/repo,local:./docs,s3:bucket)",
    },
    "web": {
        "PARALLEL_API_KEY": "Premium web search (optional — keyless Exa fallback used otherwise)",
        "EXA_API_KEY": "Raises Exa rate limits (optional)",
    },
    "google": {
        "GOOGLE_CLIENT_ID": "Google OAuth (Drive + Gmail + Calendar)",
        "GOOGLE_CLIENT_SECRET": "Google OAuth",
        "GOOGLE_PROJECT_ID": "Google OAuth",
    },
    "slack": {
        "SLACK_BOT_TOKEN": "Scout's Slack bot token — enables SlackContext + SlackTools",
        "SLACK_SIGNING_SECRET": "Verifies inbound Slack events",
    },
    "github": {
        "GITHUB_ACCESS_TOKEN": "Optional PAT — public repos clone tokenless",
        "REPOS_DIR": "Clone cache for GithubContext / GithubBackend",
    },
    "s3": {
        "AWS_ACCESS_KEY_ID": "AWS credentials for S3Context / S3Backend",
        "AWS_SECRET_ACCESS_KEY": "AWS credentials for S3Context / S3Backend",
        "AWS_REGION": "AWS region",
    },
    "db": {
        "DB_HOST": "Postgres host (default localhost)",
        "DB_PORT": "Postgres port (default 5432)",
        "DB_USER": "Postgres user (default ai)",
        "DB_DATABASE": "Postgres database (default ai)",
    },
    "outbound": {
        "SCOUT_ALLOW_SENDS": "When true, Leader can send Gmail / modify Calendar; default drafts-only",
    },
}


@tool
def health(target_id: str) -> str:
    """Health-check one target by id.

    Args:
        target_id: ``'wiki'`` for the wiki, or a context id from
            ``list_contexts`` (e.g. ``'slack'``, ``'github:agno-agi/agno'``).

    Returns:
        JSON ``{"id": ..., "state": ..., "detail": ..., "kind": ...}``.
    """
    from scout.tools.ask_context import get_contexts, get_wiki

    wiki = get_wiki()
    if target_id == "wiki":
        if wiki is None:
            return json.dumps({"id": "wiki", "state": "disconnected", "detail": "wiki not configured"})
        h = wiki.health()
        return json.dumps({"id": "wiki", "kind": wiki.kind, "state": h.state.value, "detail": h.detail})

    for ctx in get_contexts():
        if ctx.id == target_id:
            try:
                h = ctx.health()
            except Exception as exc:
                return json.dumps(
                    {
                        "id": target_id,
                        "kind": ctx.kind,
                        "state": "disconnected",
                        "detail": f"{type(exc).__name__}: {exc}",
                    }
                )
            return json.dumps({"id": target_id, "kind": ctx.kind, "state": h.state.value, "detail": h.detail})

    return json.dumps({"error": f"unknown target {target_id!r}"})


@tool
def health_all() -> str:
    """Health-check the wiki + every registered context.

    Returns:
        JSON list of ``{id, kind, state, detail}``.
    """
    from scout.tools.ask_context import get_contexts, get_wiki

    rows: list[dict] = []
    wiki = get_wiki()
    if wiki is not None:
        h = wiki.health()
        rows.append({"id": "wiki", "kind": wiki.kind, "state": h.state.value, "detail": h.detail})

    for ctx in get_contexts():
        try:
            h = ctx.health()
            rows.append({"id": ctx.id, "kind": ctx.kind, "state": h.state.value, "detail": h.detail})
        except Exception as exc:
            rows.append(
                {"id": ctx.id, "kind": ctx.kind, "state": "disconnected", "detail": f"{type(exc).__name__}: {exc}"}
            )
    return json.dumps(rows)


@tool
def db_health() -> str:
    """Check Postgres connectivity and scout_* table presence.

    Returns:
        JSON ``{"state": ..., "tables": {...}, "detail": ...}``.
    """
    from sqlalchemy import text

    from db import SCOUT_SCHEMA, get_readonly_engine

    expected = ("scout_contacts", "scout_projects", "scout_notes", "scout_decisions")
    try:
        engine = get_readonly_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
                {"schema": SCOUT_SCHEMA},
            ).all()
    except Exception as exc:
        return json.dumps({"state": "disconnected", "detail": f"{type(exc).__name__}: {exc}"})

    present = {r[0] for r in rows}
    table_status = {name: (name in present) for name in expected}
    missing = [name for name, ok in table_status.items() if not ok]
    state = "connected" if not missing else "degraded"
    detail = "all expected tables present" if not missing else f"missing: {missing}"
    return json.dumps({"state": state, "tables": table_status, "detail": detail})


@tool
def env_report() -> str:
    """Report which environment variables are set, grouped by integration.

    Never leaks values — reports presence only ("set" / "missing") plus
    the description of what the variable unlocks.
    """
    from os import getenv

    lines: list[str] = []
    for group, vars_ in _EXPECTED_ENV.items():
        lines.append(f"## {group}")
        for name, desc in vars_.items():
            present = "set" if getenv(name) else "missing"
            lines.append(f"- `{name}` ({present}) — {desc}")
        lines.append("")
    return "\n".join(lines)
