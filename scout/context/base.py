"""Scout context + wiki protocols — moves to agno.context when stable."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class HealthState(str, Enum):
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"  # includes unconfigured — detail carries the reason


@dataclass
class HealthStatus:
    state: HealthState
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state == HealthState.CONNECTED


@dataclass
class Entry:
    """A pointer to something stored in the wiki, returned by ingest."""

    id: str  # wiki-local stable id
    name: str  # human-readable
    kind: str = "file"
    path: str | None = None


@dataclass
class Hit:
    """A grounding pointer inside an Answer."""

    entry_id: str
    name: str
    snippet: str | None = None
    source_url: str | None = None


@dataclass
class Answer:
    """What a Context returns from query()."""

    text: str
    hits: list[Hit] = field(default_factory=list)


@runtime_checkable
class Context(Protocol):
    """Read-only source. Query + health.

    Implementations are cheap to instantiate. They do NOT perform
    network I/O at __init__ — health() is the place for first-touch
    checks.
    """

    id: str  # e.g. "slack", "gmail", "github:agno-agi/agno", "local:./docs"
    name: str  # human-readable
    kind: str  # "local", "github", "s3", "slack", "gmail", "drive", "wiki"

    def health(self) -> HealthStatus: ...

    def query(
        self,
        question: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> Answer: ...


@runtime_checkable
class WikiBackend(Protocol):
    """Minimal I/O abstraction for WikiContext's substrate.

    Three implementations: LocalBackend (disk), GithubBackend (git repo),
    S3Backend (bucket + prefix). Each handles its own concurrency.
    """

    kind: str  # "local", "github", "s3"

    def health(self) -> HealthStatus: ...
    def list_paths(self, prefix: str = "") -> list[str]: ...
    def read_bytes(self, path: str) -> bytes: ...
    def write_bytes(self, path: str, content: bytes) -> None: ...
    def delete(self, path: str) -> None: ...


# WikiContext is a concrete class, not a protocol. There is exactly one.
# Defined in scout/context/wiki.py. Implements Context + adds ingest/compile.
# Takes a WikiBackend in its constructor.
