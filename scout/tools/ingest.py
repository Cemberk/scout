"""Ingest tools for the Engineer agent.

§7.1 surface: ``ingest_url``, ``ingest_text``, ``trigger_compile`` — all
act on **the wiki** (the one WikiContext). They resolve the active
WikiContext through ``scout.tools.ask_context.get_wiki()`` which is
populated at startup from the ``SCOUT_WIKI`` env.
"""

from __future__ import annotations

import json
import logging

from agno.tools import tool

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# §7.1 surface — wiki-backed tools for the Engineer.
# ---------------------------------------------------------------------------


@tool
def ingest_url(url: str, title: str, tags: list[str] | None = None) -> str:
    """Ingest a URL into the wiki. Writes raw/ via the active backend.

    Args:
        url: The source URL.
        title: Human-readable title — drives the slug.
        tags: Optional list of topic tags.

    Returns:
        JSON ``{"status": "ingested"|"error", "entry_id": ..., "detail": ...}``.
    """
    # Local import to avoid a cycle with scout.tools.ask_context.
    from scout.tools.ask_context import get_wiki

    wiki = get_wiki()
    if wiki is None:
        return json.dumps({"status": "error", "detail": "wiki not configured"})
    try:
        entry = wiki.ingest_url(url, title=title, tags=tags)
    except Exception as exc:
        log.exception("ingest_url failed for %s", url)
        return json.dumps({"status": "error", "detail": f"{type(exc).__name__}: {exc}"})
    return json.dumps({"status": "ingested", "entry_id": entry.id, "name": entry.name, "path": entry.path})


@tool
def ingest_text(text: str, title: str, tags: list[str] | None = None) -> str:
    """Ingest raw text into the wiki. Writes raw/ via the active backend.

    Args:
        text: The markdown body.
        title: Required — drives the slug.
        tags: Optional topic tags.

    Returns:
        JSON ``{"status": "ingested"|"error", "entry_id": ..., "detail": ...}``.
    """
    from scout.tools.ask_context import get_wiki

    wiki = get_wiki()
    if wiki is None:
        return json.dumps({"status": "error", "detail": "wiki not configured"})
    if not title:
        return json.dumps({"status": "error", "detail": "title required"})
    try:
        entry = wiki.ingest_text(text, title=title, tags=tags)
    except Exception as exc:
        log.exception("ingest_text failed")
        return json.dumps({"status": "error", "detail": f"{type(exc).__name__}: {exc}"})
    return json.dumps({"status": "ingested", "entry_id": entry.id, "name": entry.name, "path": entry.path})


@tool
def trigger_compile(force: bool = False) -> str:
    """Run one wiki compile pass. Returns the compile report.

    Args:
        force: Recompile even unchanged entries.

    Returns:
        JSON ``{"status": "ok"|"error", "counts": {...}, "detail": ...}``.
    """
    from scout.tools.ask_context import get_wiki

    wiki = get_wiki()
    if wiki is None:
        return json.dumps({"status": "error", "detail": "wiki not configured"})
    try:
        counts = wiki.compile(force=force)
    except Exception as exc:
        log.exception("trigger_compile failed")
        return json.dumps({"status": "error", "detail": f"{type(exc).__name__}: {exc}"})
    return json.dumps({"status": "ok", "counts": counts})


