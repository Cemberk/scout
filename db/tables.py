"""
Database Tables
===============

Idempotent SQL bootstrap for Scout's own tables. Called from app startup.

We deliberately don't pull in Alembic — the surface is small and the
agno framework owns the heavy schema (sessions, knowledge vectors). The
DDL here is ``CREATE TABLE IF NOT EXISTS`` + ``ADD COLUMN IF NOT EXISTS``
so reruns are safe.

User data (canonical, Day-1 shape for the Engineer agent):
- ``scout.scout_contacts``  — people: name, emails, phone, tags, notes.
- ``scout.scout_projects``  — things in motion: name, status, tags.
- ``scout.scout_notes``     — free-form notes: title, body, tags, source_url.

Every user-data table carries the same standard columns:
``id SERIAL PK``, ``user_id TEXT NOT NULL``, ``created_at TIMESTAMPTZ``.
Beyond these three, the Engineer agent creates tables on demand.
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
]


def create_tables() -> None:
    """Apply the idempotent DDL. Safe to call on every startup."""
    engine = get_sql_engine()
    with engine.begin() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))


if __name__ == "__main__":
    create_tables()
    print("Scout tables applied.")
