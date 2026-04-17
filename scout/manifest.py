"""
Manifest — runtime capability registry
======================================

The Manifest is the small (~1–2K tokens) document that tells every agent
prompt which sources are reachable right now, in what mode, with what
capabilities. It is rebuilt:

- once at startup (lifespan hook in app.main)
- on the source-health-check cron (every 15 min)
- on demand via POST /manifest/reload

The Manifest also gates tool registration: a Navigator never gets a tool
that points at a `compile-only` source (e.g. `context/raw/`). That rule
isn't a prompt-level instruction — it's a code-level constraint enforced
here so that prompt drift can't break it.

The Manifest is held in-memory and mirrored to scout.scout_sources for
inspection / restart resilience.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock

logger = logging.getLogger(__name__)

from sqlalchemy import Engine, text

from db.session import SCOUT_SCHEMA, get_sql_engine
from scout.config import WORKSPACE_ID
from scout.sources import get_sources, reload_sources
from scout.sources.base import HealthState, Source

_TABLE = f"{SCOUT_SCHEMA}.scout_sources"
_lock = Lock()

# Cached engine — see compile_state.py for the same pattern + reasoning.
_engine: Engine | None = None
_engine_lock = Lock()


def _engine_for_manifest() -> Engine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = get_sql_engine()
    return _engine


@dataclass
class SourceState:
    id: str
    name: str
    kind: str
    compile: bool
    live_read: bool
    capabilities: list[str]
    status: str  # HealthState value
    detail: str
    last_health_at: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Manifest:
    workspace_id: str
    sources: dict[str, SourceState] = field(default_factory=dict)
    built_at: str = ""

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, workspace_id: str = WORKSPACE_ID, *, reload: bool = False) -> "Manifest":
        srcs: tuple[Source, ...] = reload_sources() if reload else get_sources()
        states: dict[str, SourceState] = {}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for s in srcs:
            try:
                health = s.health()
                caps = s.capabilities()
            except Exception as e:  # never let a broken source break startup
                states[s.id] = SourceState(
                    id=s.id,
                    name=s.name,
                    kind=type(s).__name__,
                    compile=bool(getattr(s, "compile", False)),
                    live_read=bool(getattr(s, "live_read", False)),
                    capabilities=[],
                    status=HealthState.DEGRADED.value,
                    detail=f"introspection failed: {e}",
                    last_health_at=now,
                )
                continue
            states[s.id] = SourceState(
                id=s.id,
                name=s.name,
                kind=type(s).__name__,
                compile=bool(getattr(s, "compile", False)),
                live_read=bool(getattr(s, "live_read", False)),
                capabilities=sorted(c.value for c in caps),
                status=health.state.value,
                detail=health.detail,
                last_health_at=now,
            )
        m = cls(workspace_id=workspace_id, sources=states, built_at=now)
        # Persist() is a side-effect for observability (GET /manifest reads
        # from the mirror table). Gating is authoritative from the in-memory
        # Manifest and must not depend on the DB being reachable — otherwise
        # the _smoke_gating CLI and any dev environment without Postgres
        # would lose the safety rail. Log and move on.
        try:
            m.persist()
        except Exception as exc:
            logger.warning("Manifest.persist() skipped: %s", exc)
        return m

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self) -> None:
        with _engine_for_manifest().begin() as conn:
            for state in self.sources.values():
                # CAST(... AS jsonb) avoids the psycopg bind-style collision
                # that `:cfg::jsonb` hits when SQLAlchemy translates named
                # params to %s.
                conn.execute(
                    text(
                        f"""INSERT INTO {_TABLE}
                               (id, kind, config_json, compile, live_read,
                                status, detail, last_health_at, workspace_id)
                           VALUES (:id, :kind, CAST(:cfg AS jsonb), :compile, :live_read,
                                   :status, :detail, NOW(), :wid)
                           ON CONFLICT (id) DO UPDATE
                               SET kind = EXCLUDED.kind,
                                   compile = EXCLUDED.compile,
                                   live_read = EXCLUDED.live_read,
                                   status = EXCLUDED.status,
                                   detail = EXCLUDED.detail,
                                   last_health_at = EXCLUDED.last_health_at,
                                   workspace_id = EXCLUDED.workspace_id,
                                   config_json = EXCLUDED.config_json"""
                    ),
                    {
                        "id": state.id,
                        "kind": state.kind,
                        "cfg": json.dumps({"capabilities": state.capabilities}),
                        "compile": state.compile,
                        "live_read": state.live_read,
                        "status": state.status,
                        "detail": state.detail,
                        "wid": self.workspace_id,
                    },
                )

    # ------------------------------------------------------------------
    # Queries used by tool builders + agents
    # ------------------------------------------------------------------

    def can_call(self, source_id: str, agent_role: str) -> bool:
        """Is this source legal for this agent right now?

        Rules (Phase 1):
          - Source must be CONNECTED (or DEGRADED — agents can try)
          - Compile-only sources are invisible to non-Compiler agents
          - Live-read=False sources are invisible to Navigator/Linter
          - Compiler can only see compile=True sources
        """
        s = self.sources.get(source_id)
        if s is None:
            return False
        if s.status not in (HealthState.CONNECTED.value, HealthState.DEGRADED.value):
            return False
        if agent_role == "compiler":
            return s.compile
        # navigator / linter / leader / researcher
        return s.live_read

    def callable_sources(self, agent_role: str) -> list[SourceState]:
        return [s for s in self.sources.values() if self.can_call(s.id, agent_role)]

    def compile_sources(self) -> list[SourceState]:
        return [s for s in self.sources.values() if s.compile]

    # ------------------------------------------------------------------
    # Prompt rendering — small markdown table for instructions
    # ------------------------------------------------------------------

    def render_for_prompt(self, agent_role: str) -> str:
        rows = self.callable_sources(agent_role)
        if not rows:
            return "_No sources are currently reachable._"
        lines = ["| Source | Mode | Capabilities | Status |", "|---|---|---|---|"]
        for s in rows:
            mode_bits = []
            if s.compile:
                mode_bits.append("compile")
            if s.live_read:
                mode_bits.append("live-read")
            lines.append(
                f"| `{s.id}` ({s.name}) | {','.join(mode_bits) or '-'} "
                f"| {','.join(s.capabilities) or '-'} | {s.status} |"
            )
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "built_at": self.built_at,
            "sources": [s.as_dict() for s in self.sources.values()],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manifest: Manifest | None = None


def get_manifest() -> Manifest:
    global _manifest
    with _lock:
        if _manifest is None:
            _manifest = Manifest.build()
        return _manifest


def reload_manifest() -> Manifest:
    global _manifest
    with _lock:
        _manifest = Manifest.build(reload=True)
        return _manifest
