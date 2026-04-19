"""
Tables
======

Idempotent SQL bootstrap for Scout's own tables. Called from app startup.

We deliberately don't pull in Alembic — the surface is small and the
agno framework owns the heavy schema (sessions, knowledge vectors). The
DDL here is ``CREATE TABLE IF NOT EXISTS`` + ``ADD COLUMN IF NOT EXISTS``
so reruns are safe.

User data (canonical, Day-1 shape for the Engineer agent):
- ``scout.scout_contacts``  — people: name, emails, phone, tags, notes.
- ``scout.scout_projects``  — things in motion: name, status, tags.
- ``scout.scout_notes``     — free-form notes: title, body, tags, source_url.
- ``scout.scout_decisions`` — decisions made: title, rationale, date, tags.

Every user-data table carries the same standard columns:
``id SERIAL PK``, ``user_id TEXT NOT NULL``, ``created_at TIMESTAMPTZ``.
Beyond these four, the Engineer agent creates tables on demand.

The old pipeline tables (``scout_compiled``, ``scout_sources``) and the
old ``scout_knowledge`` routing store are dropped on startup — their
replacement lives inside WikiContext's backend (state JSON) and in
``scout_learnings`` respectively.
"""

from __future__ import annotations

from sqlalchemy import text

from db.session import SCOUT_SCHEMA, get_sql_engine

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {SCOUT_SCHEMA}",
    # ----- User data (canonical) -------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS {SCOUT_SCHEMA}.scout_contacts (
        id              SERIAL PRIMARY KEY,
        name            TEXT NOT NULL,
        emails          TEXT[] NOT NULL DEFAULT '{{}}',
        phone           TEXT,
        tags            TEXT[] NOT NULL DEFAULT '{{}}',
        notes           TEXT,
        user_id         TEXT NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {SCOUT_SCHEMA}.scout_projects (
        id              SERIAL PRIMARY KEY,
        name            TEXT NOT NULL,
        status          TEXT,
        tags            TEXT[] NOT NULL DEFAULT '{{}}',
        user_id         TEXT NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {SCOUT_SCHEMA}.scout_notes (
        id              SERIAL PRIMARY KEY,
        title           TEXT NOT NULL,
        body            TEXT NOT NULL DEFAULT '',
        tags            TEXT[] NOT NULL DEFAULT '{{}}',
        source_url      TEXT,
        user_id         TEXT NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {SCOUT_SCHEMA}.scout_decisions (
        id              SERIAL PRIMARY KEY,
        title           TEXT NOT NULL,
        rationale       TEXT NOT NULL DEFAULT '',
        made_at         DATE,
        tags            TEXT[] NOT NULL DEFAULT '{{}}',
        user_id         TEXT NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
]

# One-shot drop of tables that belong to the old source/compile/manifest
# layer. Runs on every startup — safe because DROP TABLE IF EXISTS is a
# no-op once the table is gone, and the replacements live elsewhere:
# - scout_compiled: state JSON inside WikiContext's backend
# - scout_sources:  env-derived at startup (SCOUT_CONTEXTS / SCOUT_WIKI)
# - scout_knowledge: routing content folds into scout_learnings
_LEGACY_DROP_TABLES = (
    "scout_compiled",
    "scout_sources",
    "scout_knowledge",
)

_LIVE_TABLES = (
    "scout_contacts",
    "scout_projects",
    "scout_notes",
    "scout_decisions",
    "scout_learnings",
)


def create_tables() -> None:
    """Apply the idempotent DDL. Safe to call on every startup."""
    engine = get_sql_engine()
    with engine.begin() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
    # Drop the legacy tables replaced by WikiContext + env-derived config.
    for table in _LEGACY_DROP_TABLES:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {SCOUT_SCHEMA}.{table} CASCADE"))
        except Exception:
            continue
    # Strip workspace_id from any live table that still has it (older installs).
    for table in _LIVE_TABLES:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {SCOUT_SCHEMA}.{table} DROP COLUMN IF EXISTS workspace_id CASCADE"))
        except Exception:
            continue


if __name__ == "__main__":
    create_tables()
    print("Scout tables applied.")
