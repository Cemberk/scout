"""Ingest tools for the Engineer agent.

New surface (§7.1): ``ingest_url``, ``ingest_text``, ``trigger_compile`` —
all act on **the wiki** (the one WikiContext). They resolve the active
WikiContext through ``scout.tools.ask_context.get_wiki()`` which is
populated at startup from the ``SCOUT_WIKI`` env.

Legacy: ``create_ingest_tools(raw_dir)`` is kept as a compat shim for
``scout/agents/compiler.py`` until that agent is deleted in sub-step 1l.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from agno.tools import tool

log = logging.getLogger(__name__)

_SHORT_HASH_LEN = 8


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-") or "untitled"


def _slug_from_url(url: str) -> str:
    """Derive a slug from the URL's final path segment."""
    parsed = urlparse(url)
    segment = (parsed.path or "").rsplit("/", 1)[-1] or parsed.netloc
    stem = segment.split("?")[0].rsplit(".", 1)[0]
    return _slugify(stem)


def _short_content_sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:_SHORT_HASH_LEN]


def _find_duplicate(raw_dir: Path, short: str) -> Path | None:
    """Return an existing raw file with this short-content-sha, if any.

    Scoped globally across `context/raw/` so the same body keyed under
    different slugs still dedups.
    """
    for candidate in raw_dir.rglob(f"*-{short}.md"):
        return candidate
    return None


def _build_frontmatter(
    title: str,
    source: str,
    tags: list[str],
    doc_type: str,
    *,
    fetched_at: str | None = None,
) -> str:
    now = fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tag_str = ", ".join(tags) if tags else ""
    return (
        f"---\n"
        f'title: "{title}"\n'
        f"source: {source}\n"
        f"fetched_at: {now}\n"
        f"tags: [{tag_str}]\n"
        f"type: {doc_type}\n"
        f"compiled: false\n"
        f"---\n\n"
    )


def _do_ingest_url(
    raw_dir: Path,
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    doc_type: str = "article",
) -> dict:
    """Core ingest-URL logic. Idempotent by content hash."""
    from scout.settings import PARALLEL_API_KEY

    raw_dir.mkdir(parents=True, exist_ok=True)

    # Fetch/extract first so we can hash the body.
    extracted = ""
    if PARALLEL_API_KEY:
        try:
            from parallel import Parallel

            client = Parallel(api_key=PARALLEL_API_KEY)
            result = client.beta.extract(urls=[url], full_content=True)
            if result and result.results:
                r = result.results[0]
                extracted = r.full_content or ""
        except Exception as e:
            extracted = f"*(Content extraction failed: {e}. Stub saved — fetch manually.)*"

    body = extracted or f"Source: {url}\n\n*(Content pending — configure PARALLEL_API_KEY or use ingest_text.)*"
    display_title = title or _slug_from_url(url).replace("-", " ").title() or url
    slug = _slugify(title) if title else _slug_from_url(url)
    short = _short_content_sha(body)

    duplicate = _find_duplicate(raw_dir, short)
    if duplicate is not None:
        return {
            "status": "duplicate",
            "path": str(duplicate.relative_to(raw_dir)),
            "content_sha": short,
        }

    filename = f"{slug}-{short}.md"
    file_path = raw_dir / filename
    frontmatter = _build_frontmatter(display_title, url, tags or [], doc_type)
    file_path.write_text(frontmatter + body + "\n")
    return {
        "status": "ingested",
        "path": str(file_path.relative_to(raw_dir)),
        "content_sha": short,
        "chars": len(body),
    }


def _do_ingest_text(
    raw_dir: Path,
    title: str,
    content: str,
    source: str = "user",
    tags: list[str] | None = None,
    doc_type: str = "notes",
) -> dict:
    """Core ingest-text logic. Idempotent by content hash."""
    if not title:
        return {"status": "error", "reason": "title required for ingest_text"}
    raw_dir.mkdir(parents=True, exist_ok=True)
    body = content or ""
    slug = _slugify(title)
    short = _short_content_sha(body)
    duplicate = _find_duplicate(raw_dir, short)
    if duplicate is not None:
        return {
            "status": "duplicate",
            "path": str(duplicate.relative_to(raw_dir)),
            "content_sha": short,
        }
    filename = f"{slug}-{short}.md"
    file_path = raw_dir / filename
    frontmatter = _build_frontmatter(title, source, tags or [], doc_type)
    file_path.write_text(frontmatter + body + "\n")
    return {
        "status": "ingested",
        "path": str(file_path.relative_to(raw_dir)),
        "content_sha": short,
        "chars": len(body),
    }


def create_ingest_tools(raw_dir: Path):
    """Create ingest tools bound to the raw/ directory.

    Args:
        raw_dir: Path to raw/ (CONTEXT_RAW_DIR).

    Returns:
        Tuple of (ingest_url, ingest_text) tool functions.
    """

    @tool
    def ingest_url(url: str, title: str | None = None, tags: list[str] | None = None, doc_type: str = "article") -> str:
        """Ingest a URL into context/raw/ as `<slug>-<short-content-sha>.md`.

        Fetches page content via Parallel (if configured) and saves it with
        YAML frontmatter. Idempotent by content hash — the same body, ingested
        twice, returns `duplicate` and leaves the original untouched.

        Args:
            url: The source URL.
            title: Optional title; if omitted, slug is derived from the URL.
            tags: Optional list of topic tags (e.g. ["rag", "retrieval"]).
            doc_type: Document type: paper, article, repo, notes, transcript, image.

        Returns:
            JSON string: `{"status": "ingested"|"duplicate", "path": ...}`.
        """
        return json.dumps(_do_ingest_url(raw_dir, url, title, tags, doc_type))

    @tool
    def ingest_text(
        title: str,
        content: str,
        source: str = "user",
        tags: list[str] | None = None,
        doc_type: str = "notes",
    ) -> str:
        """Ingest text into context/raw/ as `<slug>-<short-content-sha>.md`.

        Idempotent by content hash — same `content` ingested twice returns
        `duplicate`.

        Args:
            title: Required title (drives the slug).
            content: The markdown body.
            source: Where the content came from ("user", URL, etc.).
            tags: Optional topic tags.
            doc_type: paper | article | repo | notes | transcript | image.

        Returns:
            JSON string: `{"status": "ingested"|"duplicate"|"error", ...}`.
        """
        return json.dumps(_do_ingest_text(raw_dir, title, content, source, tags, doc_type))

    return ingest_url, ingest_text


# ---------------------------------------------------------------------------
# New surface (§7.1) — wiki-backed tools for the Engineer.
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
