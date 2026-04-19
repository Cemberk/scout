"""
Tables
======

Idempotent SQL bootstrap for Scout's own tables. Called from app startup.

We deliberately don't pull in Alembic — the v3 surface is small and the
agno framework owns the heavy schema (sessions, knowledge vectors). The
DDL here is ``CREATE TABLE IF NOT EXISTS`` + ``ADD COLUMN IF NOT EXISTS``
so reruns are safe.

Two groups of tables live here:

Pipeline state (internal):
- ``scout.scout_compiled``  — per-entry compile state, replaces the old
  on-disk ``.state.json`` + ``.manifest.json`` files.
- ``scout.scout_sources``   — persistent source state for the Manifest.

User data (canonical, Day-1 shape for the Engineer agent):
- ``scout.scout_contacts``  — people: name, emails, phone, tags, notes.
- ``scout.scout_projects``  — things in motion: name, status, tags.
- ``scout.scout_notes``     — free-form notes: title, body, tags, source_url.
- ``scout.scout_decisions`` — decisions made: title, rationale, date, tags.

Every user-data table carries the same standard columns:
``id SERIAL PK``, ``user_id TEXT NOT NULL``, ``created_at TIMESTAMPTZ``.
Beyond these three, the Engineer agent creates tables on demand.
"""

from __future__ import annotations

from sqlalchemy import text

from db.session import SCOUT_SCHEMA, get_sql_engine

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {SCOUT_SCHEMA}",
    # ----- Pipeline state ---------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS {SCOUT_SCHEMA}.scout_compiled (
        id                      SERIAL PRIMARY KEY,
        source_id               TEXT NOT NULL,
        entry_id                TEXT NOT NULL,
        source_hash             TEXT NOT NULL,
        compiler_output_hash    TEXT NOT NULL DEFAULT '',
        wiki_path               TEXT NOT NULL,
        compiled_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        compiled_by             TEXT NOT NULL DEFAULT 'scout-compiler-v3',
        user_edited             BOOLEAN NOT NULL DEFAULT FALSE,
        needs_split             BOOLEAN NOT NULL DEFAULT FALSE,
        UNIQUE (source_id, entry_id)
    )
    """,
    # Backfill for pre-spec installs.
    f"ALTER TABLE {SCOUT_SCHEMA}.scout_compiled ADD COLUMN IF NOT EXISTS compiler_output_hash TEXT NOT NULL DEFAULT ''",
    f"ALTER TABLE {SCOUT_SCHEMA}.scout_compiled ADD COLUMN IF NOT EXISTS needs_split BOOLEAN NOT NULL DEFAULT FALSE",
    f"""
    CREATE INDEX IF NOT EXISTS idx_scout_compiled_lookup
        ON {SCOUT_SCHEMA}.scout_compiled (source_id, entry_id)
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {SCOUT_SCHEMA}.scout_sources (
        id              TEXT PRIMARY KEY,
        kind            TEXT NOT NULL,
        config_json     JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        compile         BOOLEAN NOT NULL DEFAULT FALSE,
        live_read       BOOLEAN NOT NULL DEFAULT TRUE,
        status          TEXT NOT NULL DEFAULT 'unknown',
        detail          TEXT NOT NULL DEFAULT '',
        last_health_at  TIMESTAMPTZ
    )
    """,
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

# Drop any lingering workspace_id columns from older installs. Idempotent:
# runs on every startup, CASCADE removes the old 3-column UNIQUE constraint
# on scout_compiled so the new 2-column one (source_id, entry_id) works.
# Safe because Phase 1 only ever wrote 'default' into these columns.
_WORKSPACE_DROP_TABLES = (
    "scout_compiled",
    "scout_sources",
    "scout_contacts",
    "scout_projects",
    "scout_notes",
    "scout_decisions",
    # agno-managed knowledge tables may also carry the column from older runs.
    "scout_knowledge",
    "scout_learnings",
)


def create_tables() -> None:
    """Apply the idempotent DDL. Safe to call on every startup."""
    engine = get_sql_engine()
    # Core DDL (CREATE TABLE IF NOT EXISTS ...) in one transaction.
    with engine.begin() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
    # Strip workspace_id from any table that still has it (from older
    # installs). Per-statement transactions so a missing agno-managed
    # table doesn't roll back the rest.
    for table in _WORKSPACE_DROP_TABLES:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {SCOUT_SCHEMA}.{table} DROP COLUMN IF EXISTS workspace_id CASCADE"))
        except Exception:
            # Table doesn't exist yet (agno creates on first insert). Next
            # startup will handle the drop.
            continue
    # After dropping the old 3-col UNIQUE via CASCADE above, make sure
    # scout_compiled has the new 2-col uniqueness (the CREATE TABLE path
    # handles fresh installs; this covers migrated ones).
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS scout_compiled_source_entry_uniq "
                    f"ON {SCOUT_SCHEMA}.scout_compiled (source_id, entry_id)"
                )
            )
    except Exception:
        pass


if __name__ == "__main__":
    create_tables()
    print("Scout tables applied.")
