"""
Migrations
==========

Idempotent SQL bootstrap for Scout's own tables. Called from app startup.

We are deliberately not pulling in Alembic — the v3 surface is small and the
agno framework owns the heavy schema (sessions, knowledge vectors). These
DDLs are CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS so reruns
are safe.

Tables owned here:
- scout.scout_compiled  — per-entry compile state, replaces the old
  on-disk .state.json + .manifest.json files
- scout.scout_sources   — persistent source state for the Manifest
- scout_knowledge / scout_learnings — `workspace_id` column added
"""

from __future__ import annotations

from sqlalchemy import text

from db.session import SCOUT_SCHEMA, get_sql_engine

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {SCOUT_SCHEMA}",
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
        workspace_id            TEXT NOT NULL DEFAULT 'default',
        UNIQUE (source_id, entry_id, workspace_id)
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
        last_health_at  TIMESTAMPTZ,
        workspace_id    TEXT NOT NULL DEFAULT 'default'
    )
    """,
]

# Columns to be added to agno-managed knowledge tables. Using
# ADD COLUMN IF NOT EXISTS keeps this safe across reruns and across
# environments where the agno tables haven't been created yet (we just
# skip those — agno will create them at first knowledge insert and a
# subsequent migration run will pick them up).
KNOWLEDGE_TABLES = ("scout_knowledge", "scout_learnings")
WORKSPACE_COLUMN = "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS workspace_id TEXT NOT NULL DEFAULT 'default'"


def run_migrations() -> None:
    engine = get_sql_engine()
    with engine.begin() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
        for table in KNOWLEDGE_TABLES:
            try:
                conn.execute(text(WORKSPACE_COLUMN.format(table=table)))
            except Exception:
                # Table doesn't exist yet — agno will create it on first insert.
                # Next startup will add the column.
                conn.rollback()
                continue
    engine.dispose()


if __name__ == "__main__":
    run_migrations()
    print("Scout migrations applied.")
