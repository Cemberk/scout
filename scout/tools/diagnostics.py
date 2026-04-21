"""Diagnostic tools for the Doctor agent.

Doctor surface:
- ``status(target_id)``  — one context.
- ``status_all()``       — every registered context.
- ``db_status()``        — Postgres connectivity + table existence.
- ``env_report()``       — env var presence (redacted, grouped by integration).
"""

from __future__ import annotations

import json
import logging

from agno.tools import tool

log = logging.getLogger(__name__)


_EXPECTED_ENV: dict[str, dict[str, str]] = {
    "core": {
        "OPENAI_API_KEY": "GPT-5.4 for every agent + embeddings",
    },
    "web": {
        "PARALLEL_API_KEY": "Premium web research (optional — keyless Exa fallback used otherwise)",
        "EXA_API_KEY": "Raises Exa rate limits (optional)",
    },
    "db": {
        "DB_HOST": "Postgres host (default localhost)",
        "DB_PORT": "Postgres port (default 5432)",
        "DB_USER": "Postgres user (default ai)",
        "DB_DATABASE": "Postgres database (default ai)",
    },
}


@tool
def status(target_id: str) -> str:
    """Status check for one context by id.

    Args:
        target_id: A context id from ``list_contexts`` (e.g. ``'web'``).

    Returns:
        JSON ``{"id": ..., "ok": ..., "detail": ...}``.
    """
    from scout.contexts import get_contexts

    for ctx in get_contexts():
        if ctx.id == target_id:
            try:
                s = ctx.status()
            except Exception as exc:
                return json.dumps({"id": target_id, "ok": False, "detail": f"{type(exc).__name__}: {exc}"})
            return json.dumps({"id": target_id, "ok": s.ok, "detail": s.detail})

    return json.dumps({"error": f"unknown target {target_id!r}"})


@tool
def status_all() -> str:
    """Status check for every registered context.

    Returns:
        JSON list of ``{id, ok, detail}``.
    """
    from scout.contexts import get_contexts

    rows: list[dict] = []
    for ctx in get_contexts():
        try:
            s = ctx.status()
            rows.append({"id": ctx.id, "ok": s.ok, "detail": s.detail})
        except Exception as exc:
            rows.append({"id": ctx.id, "ok": False, "detail": f"{type(exc).__name__}: {exc}"})
    return json.dumps(rows)


@tool
def db_status() -> str:
    """Check Postgres connectivity and ``scout_*`` table presence.

    Returns:
        JSON ``{"ok": ..., "tables": {...}, "detail": ...}``.
    """
    from sqlalchemy import text

    from db import SCOUT_SCHEMA, get_readonly_engine

    expected = ("scout_contacts", "scout_projects", "scout_notes")
    try:
        engine = get_readonly_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
                {"schema": SCOUT_SCHEMA},
            ).all()
    except Exception as exc:
        return json.dumps({"ok": False, "detail": f"{type(exc).__name__}: {exc}"})

    present = {r[0] for r in rows}
    table_status = {name: (name in present) for name in expected}
    missing = [name for name, ok in table_status.items() if not ok]
    detail = "all expected tables present" if not missing else f"missing: {missing}"
    return json.dumps({"ok": not missing, "tables": table_status, "detail": detail})


@tool
def env_report() -> str:
    """Report which environment variables are set, grouped by integration.

    Never leaks values — reports presence only ("set" / "missing").
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
