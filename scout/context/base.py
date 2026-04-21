"""Context provider + wiki-backend base types.

- ``ContextProvider`` (ABC) — every context subclasses this. Subclasses
  wire a backend in ``__init__``, implement ``query()`` + ``health()``,
  and inherit ``get_tools()``. Backend owns substrate config; provider
  is pure business logic.
- ``WikiBackend`` (Protocol) — raw-bytes I/O abstraction used *only* by
  ``WikiContextProvider``. Structural Protocol because the three
  implementations — Local / Github / S3 — share shape through duck
  typing, not inheritance.

Reference spec for the Agno move: [tmp/context_provider.md](../../tmp/context_provider.md).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Query returns
# ---------------------------------------------------------------------------


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
    """What a ContextProvider returns from query()."""

    text: str
    hits: list[Hit] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ContextProvider base class
# ---------------------------------------------------------------------------


class ContextProvider(ABC):
    """Base class for every context provider.

    Subclasses MUST:
    - set ``kind`` as a class attribute (e.g. ``"wiki"``, ``"slack"``, ``"local"``)
    - set ``id`` + ``name`` (class attrs or in ``__init__``)
    - implement ``query(question, *, limit)`` → ``Answer``
    - implement ``health()`` → ``HealthStatus``

    Subclasses MAY override:
    - ``_granular_tools()`` to expose substrate-specific tools directly
      (e.g. a file provider exposing ``list_dir`` / ``read_file`` / ``grep``
      so a developer's agent can use them without going through the
      provider's sub-agent).

    Developers wire a provider onto their agent via ``.get_tools()``:

        agent = Agent(tools=[*my_context.get_tools(), *other_tools])

    No ``context=`` parameter on ``Agent`` — composition stays explicit.
    """

    # Subclasses set these.
    id: str  # e.g. "wiki", "slack", "github:agno-agi/agno", "local:./docs"
    name: str  # human-readable
    kind: str  # "wiki", "local", "github", "s3", "slack", "gmail", "drive"

    @abstractmethod
    def query(self, question: str, *, limit: int = 10) -> Answer:
        """Answer a question by exploring the substrate.

        Agentic by default — most implementations wrap a sub-agent with
        substrate-specific tools. Simpler ones may call a backend API
        directly and pack the result into ``Answer``.
        """

    @abstractmethod
    def health(self) -> HealthStatus:
        """Is the substrate reachable?"""

    def get_tools(self, *, granular: bool = False) -> list:
        """Return tools a developer wires onto their Agent.

        Default: one ``@tool`` named ``query_<sanitized_id>`` that wraps
        ``self.query()`` and returns a JSON string for the model.

        ``granular=True`` returns substrate-specific tools instead
        (``list_dir`` / ``read_file`` / ``grep`` for a file provider,
        etc.) — subclasses override ``_granular_tools()`` to implement.
        """
        if granular:
            return self._granular_tools()
        return [self._query_tool()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _query_tool(self):
        """Build one @tool wrapping ``self.query()``.

        Tool name is ``query_<sanitized_id>``. The wrapper catches
        exceptions so the model sees ``{"error": ...}`` instead of a
        crash. Output runs through ``scout.tools.redactor.redact`` —
        defensive scrub for secret-shaped strings the substrate might
        have surfaced.
        """
        from agno.tools import tool

        from scout.tools.redactor import redact

        provider = self
        tool_name = f"query_{_sanitize_id(self.id)}"

        @tool(name=tool_name)
        def _query(question: str, limit: int = 10) -> str:
            try:
                answer = provider.query(question, limit=limit)
            except Exception as exc:
                return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
            hits = []
            for h in answer.hits:
                hit = dict(h.__dict__)
                if hit.get("snippet"):
                    hit["snippet"] = redact(hit["snippet"])
                hits.append(hit)
            return json.dumps({"answer": redact(answer.text), "hits": hits})

        return _query

    def _granular_tools(self) -> list:
        """Override to expose substrate-specific tools. Default: just the query tool."""
        return [self._query_tool()]


def _sanitize_id(raw: str) -> str:
    """Turn a context id into a valid tool-name suffix.

    ``"github:agno-agi/agno"`` → ``"github_agno_agi_agno"``.
    ``"local:./docs"``         → ``"local_docs"``.
    Lowercases, replaces non-alphanumerics with ``_``, collapses runs.
    """
    import re

    s = raw.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "context"


# ---------------------------------------------------------------------------
# WikiBackend — still a structural Protocol (only used by WikiContextProvider)
# ---------------------------------------------------------------------------


@runtime_checkable
class WikiBackend(Protocol):
    """Raw-bytes I/O abstraction for ``WikiContextProvider``.

    Three implementations ship — ``LocalWikiBackend``, ``GithubWikiBackend``,
    ``S3WikiBackend``. Each handles its own concurrency (Local: none;
    Github: pull-rebase retry; S3: conditional PUT on state).
    """

    kind: str  # "local", "github", "s3"

    def health(self) -> HealthStatus: ...
    def list_paths(self, prefix: str = "") -> list[str]: ...
    def read_bytes(self, path: str) -> bytes: ...
    def write_bytes(self, path: str, content: bytes) -> None: ...
    def delete(self, path: str) -> None: ...


__all__ = [
    "Answer",
    "ContextProvider",
    "Entry",
    "HealthState",
    "HealthStatus",
    "Hit",
    "WikiBackend",
]
