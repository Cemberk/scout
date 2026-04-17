"""
Source-backed tools
===================

A small set of dispatch tools the agents call to talk to any registered
Source. The Manifest gates which sources each agent can reach: tools that
target unreachable sources return an explicit "X isn't reachable" message
rather than silently falling back, per spec §7 governance.

These tools are deliberately uniform across all sources. The Source
abstraction is what lets us not write per-source tool families.
"""

from __future__ import annotations

import json

from agno.tools import tool

from scout.manifest import get_manifest
from scout.sources import get_source
from scout.sources.base import FindKind, NotSupported
from scout.tools.redactor import redact


def _refuse(source_id: str, reason: str) -> str:
    return json.dumps({"status": "refused", "source_id": source_id, "reason": reason})


def create_source_tools(agent_role: str):
    """Return a list of source-dispatch tools scoped to one agent role.

    `agent_role` is one of: 'navigator', 'compiler', 'linter', 'researcher'.
    """

    @tool
    def list_sources() -> str:
        """List sources callable by this agent right now (with capabilities and status).

        Returns a JSON array of {id, name, mode, capabilities, status, detail}.
        Use this before calling source_list / source_read / source_find to
        confirm what's reachable.
        """
        manifest = get_manifest()
        rows = manifest.callable_sources(agent_role)
        return redact(json.dumps([r.as_dict() for r in rows], indent=2))

    @tool
    def source_list(source_id: str, path: str = "") -> str:
        """Enumerate entries in a source.

        Args:
            source_id: A source from list_sources (e.g. 'local:wiki', 'drive').
            path: Optional sub-path or container id inside the source.

        Returns: JSON array of entries with id, name, kind, size, modified_at.
        """
        manifest = get_manifest()
        if not manifest.can_call(source_id, agent_role):
            return _refuse(source_id, "not reachable for this agent")
        s = get_source(source_id)
        if s is None:
            return _refuse(source_id, "unknown source id")
        try:
            entries = s.list(path)
        except Exception as e:
            return _refuse(source_id, f"list failed: {e}")
        return redact(
            json.dumps(
                [
                    {
                        "id": e.id,
                        "name": e.name,
                        "kind": e.kind,
                        "size": e.size,
                        "modified_at": e.modified_at,
                    }
                    for e in entries
                ],
                indent=2,
            )
        )

    @tool
    def source_find(source_id: str, query: str, kind: str = "lexical") -> str:
        """Locate entries inside a source.

        `kind` is one of: lexical, native, semantic. Each source declares
        what it supports — check capabilities via list_sources first.

        Returns JSON array of {entry_id, name, score, snippet, source_url, citation_hint}.
        """
        manifest = get_manifest()
        if not manifest.can_call(source_id, agent_role):
            return _refuse(source_id, "not reachable for this agent")
        s = get_source(source_id)
        if s is None:
            return _refuse(source_id, "unknown source id")
        try:
            find_kind = FindKind(kind)
        except ValueError:
            return _refuse(source_id, f"unknown find kind {kind!r}")
        try:
            hits = s.find(query, find_kind)
        except NotSupported as e:
            return _refuse(source_id, str(e))
        except Exception as e:
            return _refuse(source_id, f"find failed: {e}")
        return redact(
            json.dumps(
                [
                    {
                        "entry_id": h.entry_id,
                        "name": h.name,
                        "score": h.score,
                        "snippet": h.snippet,
                        "source_url": h.source_url,
                        "citation_hint": h.citation_hint,
                    }
                    for h in hits
                ],
                indent=2,
            )
        )

    @tool
    def source_read(source_id: str, entry_id: str, max_chars: int = 30_000) -> str:
        """Read one entry's text content (plus citation info).

        Returns JSON: {text, mime, source_url, citation_hint, truncated}.
        Binary entries return text=null with mime set.
        """
        manifest = get_manifest()
        if not manifest.can_call(source_id, agent_role):
            return _refuse(source_id, "not reachable for this agent")
        s = get_source(source_id)
        if s is None:
            return _refuse(source_id, "unknown source id")
        try:
            content = s.read(entry_id)
        except Exception as e:
            return _refuse(source_id, f"read failed: {e}")
        text = content.text
        truncated = False
        if text and len(text) > max_chars:
            text = text[:max_chars]
            truncated = True
        return redact(
            json.dumps(
                {
                    "text": text,
                    "mime": content.mime,
                    "source_url": content.source_url,
                    "citation_hint": content.citation_hint,
                    "truncated": truncated,
                }
            )
        )

    return [list_sources, source_list, source_find, source_read]
