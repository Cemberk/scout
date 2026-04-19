"""Ingest tools — fetch URLs and save text to raw/ with frontmatter.

Spec §5a filename convention:

    context/raw/<slug>-<short-content-sha>.md

where `short-content-sha = sha256(body)[:8]`. Idempotency comes from the
hash: the same URL ingested on two different days yields the same
`content_sha` and is skipped as a duplicate. No date in the filename —
date-in-filename was what produced the "same source_hash, two raw files,
one orphan compiled article" drift in the prior build.

We still maintain `context/raw/.manifest.json` as extra bookkeeping;
it is not load-bearing for dedup.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from agno.tools import tool

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


def _read_manifest(raw_dir: Path) -> list[dict]:
    manifest_path = raw_dir / ".manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())  # type: ignore[no-any-return]
    return []


def _write_manifest(raw_dir: Path, manifest: list[dict]) -> None:
    manifest_path = raw_dir / ".manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


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


def _record_ingest(raw_dir: Path, filename: str, title: str, source: str) -> None:
    manifest = _read_manifest(raw_dir)
    manifest.append(
        {
            "file": filename,
            "title": title,
            "source": source,
            "ingested": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "compiled": False,
        }
    )
    _write_manifest(raw_dir, manifest)


def _do_ingest_url(
    raw_dir: Path,
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    doc_type: str = "article",
) -> dict:
    """Core ingest-URL logic. Spec §5a idempotent-by-content-hash."""
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
    _record_ingest(raw_dir, filename, display_title, url)
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
    """Core ingest-text logic. Spec §5a idempotent-by-content-hash."""
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
    _record_ingest(raw_dir, filename, title, source)
    return {
        "status": "ingested",
        "path": str(file_path.relative_to(raw_dir)),
        "content_sha": short,
        "chars": len(body),
    }


def create_ingest_tools(raw_dir: Path):
    """Create ingest tools bound to the raw/ directory.

    Args:
        raw_dir: Path to raw/ (resolved from SCOUT_CONTEXT_DIR).

    Returns:
        List of tool functions.
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

    @tool
    def read_manifest() -> str:
        """Read the raw/ manifest to see all ingested documents and their compile status.

        Returns:
            JSON string of the manifest entries.
        """
        manifest = _read_manifest(raw_dir)
        if not manifest:
            return "No documents ingested yet. The raw/ directory is empty."
        return json.dumps(manifest, indent=2)

    @tool
    def update_manifest_compiled(filename: str) -> str:
        """Mark a raw document as compiled in the manifest.

        Call this after successfully compiling a raw document into wiki articles.

        Args:
            filename: The filename in raw/ to mark as compiled.

        Returns:
            Confirmation message.
        """
        manifest = _read_manifest(raw_dir)
        for entry in manifest:
            if entry["file"] == filename:
                entry["compiled"] = True
                _write_manifest(raw_dir, manifest)
                return f"Marked as compiled: {filename}"
        return f"Not found in manifest: {filename}"

    return [ingest_url, ingest_text, read_manifest, update_manifest_compiled]
