"""
Compile state — Postgres-backed replacement for raw/.manifest.json + wiki/.state.json
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from sqlalchemy import Engine, text

from db.session import SCOUT_SCHEMA, get_sql_engine
from scout.config import WORKSPACE_ID

_TABLE = f"{SCOUT_SCHEMA}.scout_compiled"

# Module-level cached engine. SQLAlchemy engines are pools; one per process
# is the correct usage. The previous version created and leaked an engine
# per call which exhausted the DB pool under any real compile load.
_engine: Engine | None = None
_engine_lock = Lock()


def _engine_for_state() -> Engine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = get_sql_engine()
    return _engine


@dataclass
class CompileRecord:
    source_id: str
    entry_id: str
    source_hash: str
    wiki_path: str
    compiled_at: str
    compiled_by: str
    user_edited: bool
    workspace_id: str = WORKSPACE_ID


def get_record(source_id: str, entry_id: str, workspace_id: str = WORKSPACE_ID) -> CompileRecord | None:
    with _engine_for_state().connect() as conn:
        row = conn.execute(
            text(
                f"""SELECT source_id, entry_id, source_hash, wiki_path, compiled_at,
                          compiled_by, user_edited, workspace_id
                   FROM {_TABLE}
                   WHERE source_id = :sid AND entry_id = :eid AND workspace_id = :wid"""
            ),
            {"sid": source_id, "eid": entry_id, "wid": workspace_id},
        ).fetchone()
    if not row:
        return None
    return CompileRecord(
        source_id=row[0],
        entry_id=row[1],
        source_hash=row[2],
        wiki_path=row[3],
        compiled_at=row[4].isoformat() if row[4] else "",
        compiled_by=row[5],
        user_edited=bool(row[6]),
        workspace_id=row[7],
    )


def upsert_record(record: CompileRecord) -> None:
    with _engine_for_state().begin() as conn:
        conn.execute(
            text(
                f"""INSERT INTO {_TABLE}
                       (source_id, entry_id, source_hash, wiki_path,
                        compiled_at, compiled_by, user_edited, workspace_id)
                   VALUES (:sid, :eid, :hash, :wpath, NOW(), :by, :edited, :wid)
                   ON CONFLICT (source_id, entry_id, workspace_id) DO UPDATE
                       SET source_hash = EXCLUDED.source_hash,
                           wiki_path   = EXCLUDED.wiki_path,
                           compiled_at = EXCLUDED.compiled_at,
                           compiled_by = EXCLUDED.compiled_by,
                           user_edited = EXCLUDED.user_edited"""
            ),
            {
                "sid": record.source_id,
                "eid": record.entry_id,
                "hash": record.source_hash,
                "wpath": record.wiki_path,
                "by": record.compiled_by,
                "edited": record.user_edited,
                "wid": record.workspace_id,
            },
        )


def list_records_for_source(source_id: str, workspace_id: str = WORKSPACE_ID) -> list[CompileRecord]:
    with _engine_for_state().connect() as conn:
        rows = conn.execute(
            text(
                f"""SELECT source_id, entry_id, source_hash, wiki_path, compiled_at,
                          compiled_by, user_edited, workspace_id
                   FROM {_TABLE}
                   WHERE source_id = :sid AND workspace_id = :wid"""
            ),
            {"sid": source_id, "wid": workspace_id},
        ).fetchall()
    return [
        CompileRecord(
            source_id=r[0],
            entry_id=r[1],
            source_hash=r[2],
            wiki_path=r[3],
            compiled_at=r[4].isoformat() if r[4] else "",
            compiled_by=r[5],
            user_edited=bool(r[6]),
            workspace_id=r[7],
        )
        for r in rows
    ]


def mark_user_edited(source_id: str, entry_id: str, workspace_id: str = WORKSPACE_ID) -> None:
    with _engine_for_state().begin() as conn:
        conn.execute(
            text(
                f"UPDATE {_TABLE} SET user_edited = TRUE "
                "WHERE source_id = :sid AND entry_id = :eid AND workspace_id = :wid"
            ),
            {"sid": source_id, "eid": entry_id, "wid": workspace_id},
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
