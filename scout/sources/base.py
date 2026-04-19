"""
Source protocol
===============

A `Source` is anything Scout can navigate: local folders, Drive, S3, Slack.
Each source declares its capabilities and is invoked through a tiny
uniform interface.

Every source supports LIST and READ. FIND is optional — callers check
`capabilities()` before dispatching.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Capability(str, Enum):
    LIST = "list"
    READ = "read"
    FIND = "find"


class HealthState(str, Enum):
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    UNCONFIGURED = "unconfigured"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """A pointer to something inside a source — file, doc, message, etc."""

    id: str  # source-local stable identifier
    name: str  # human-readable name (filename, doc title, ...)
    kind: str = "file"  # file / folder / message / thread / row
    path: str | None = None  # logical path inside the source, if applicable
    size: int | None = None
    modified_at: str | None = None  # ISO 8601


@dataclass
class Content:
    """Bytes or text + the citation hint that points back to the original."""

    bytes: bytes | None = None
    text: str | None = None
    mime: str = "application/octet-stream"
    source_url: str | None = None  # e.g. https://drive.google.com/file/d/...
    citation_hint: str | None = None  # e.g. "ACME/HR/Handbook.pdf §4"


@dataclass
class Hit:
    """A `find` result — pointer to an entry plus snippet and score."""

    entry_id: str
    name: str
    score: float = 0.0
    snippet: str | None = None
    source_url: str | None = None
    citation_hint: str | None = None


@dataclass
class HealthStatus:
    state: HealthState
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state == HealthState.CONNECTED


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotSupported(Exception):
    """Raised when a source doesn't support a requested operation."""


class SourceError(Exception):
    """Generic source-side error (network, auth, etc.)."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Source(Protocol):
    """The Scout Source protocol.

    Implementations should be cheap to instantiate and stateful only with
    respect to caches/clients. They must NOT perform network I/O at __init__
    time — `health()` is the place for first-touch checks.
    """

    id: str
    name: str
    compile: bool
    live_read: bool

    def list_entries(self, path: str = "") -> list[Entry]:
        """Enumerate entries. May raise NotSupported."""
        ...

    def read(self, entry_id: str) -> Content:
        """Read one entry's content. Includes source_url + citation_hint."""
        ...

    def health(self) -> HealthStatus:
        """Cheap reachability check — used by Manifest builder + cron."""
        ...

    def capabilities(self) -> "set[Capability]":
        """Declared capabilities — Manifest gates tool registration on this."""
        ...

    def find(self, query: str) -> list[Hit]:
        """Locate entries. Raises NotSupported if the source has no find."""
        ...
