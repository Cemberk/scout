"""
Compile pipeline runner
=======================

Iterates `[s for s in sources if s.compile]`, diffs against `scout_compiled`,
and produces Obsidian-compatible markdown under `context/compiled/articles/`.

Per spec §3 — "the heart of Scout. A developer reading the repo should
study the Compiler first."

Boundary contract:
- Reads from any source through the Source protocol (no direct fs reads
  beyond what LocalFolderSource exposes).
- Writes only under SCOUT_COMPILED_DIR/articles/.
- Records every successful compile in scout.scout_compiled.
- Inserts a Wiki: row in scout_knowledge for each new article.
- Never overwrites an article whose record has user_edited=True or
  whose on-disk frontmatter declares it. Writes a sibling instead and
  flags the previous record as stale (the Linter surfaces it).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agno.agent import Agent
from agno.models.anthropic import Claude

from scout.compile_state import (
    CompileRecord,
    get_record,
    upsert_record,
)
from scout.config import SCOUT_COMPILED_DIR, SCOUT_VOICE_DIR, WORKSPACE_ID
from scout.sources import get_source, get_sources
from scout.sources.base import Source

ARTICLES_DIR = SCOUT_COMPILED_DIR / "articles"
INDEX_PATH = SCOUT_COMPILED_DIR / "index.md"
COMPILER_VERSION = "scout-compiler-v3"

# Spec §5: "If content.text exceeds 20,000 characters, the Compiler still
# emits a single article, adds needs_split: true to the article's
# frontmatter, and writes a `Linter:` row so the Sunday lint pass flags
# it." We use `Discovery:` (existing prefix in scout_knowledge) rather
# than invent a new one — see tmp/spec-diff.md A3.
NEEDS_SPLIT_THRESHOLD = 20_000


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class CompileResult:
    source_id: str
    entry_id: str
    status: str  # "compiled" | "skipped-unchanged" | "skipped-user-edited" | "skipped-empty" | "error"
    wiki_path: str | None = None
    detail: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")[:80] or "article"


def _short_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _voice_guide() -> str:
    p = SCOUT_VOICE_DIR / "wiki-article.md"
    if p.exists():
        return p.read_text()
    return ""


def _read_disk_user_edited(article_path: Path) -> bool:
    """Inspect on-disk frontmatter to honour user edits Compiler hasn't recorded yet."""
    if not article_path.exists():
        return False
    text = article_path.read_text(errors="replace")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 4)
    if end < 0:
        return False
    front = text[4:end]
    for line in front.splitlines():
        if line.strip().startswith("user_edited:"):
            value = line.split(":", 1)[1].strip().lower()
            return value in ("true", "yes", "1")
    return False


# ---------------------------------------------------------------------------
# Compile prompt
# ---------------------------------------------------------------------------


_COMPILE_INSTRUCTIONS_TMPL = """\
You are the Scout Compiler. Convert the SOURCE below into Obsidian-compatible
markdown articles, following the voice guide.

Output rules:
- Output ONE OR MORE complete markdown articles, each preceded by an
  HR line containing exactly: `===ARTICLE===`
- Each article must start with full YAML frontmatter as specified in
  the voice guide. Set user_edited: false on all output.
- Filename slug for each article will be derived from its title — keep
  titles short, distinct, and noun-phrase shaped.
- Tags: 2–5 lowercase kebab-case.
- Backlinks: include 1–4 likely sibling articles even if they don't
  exist yet. The Linter resolves [[?]] gaps.
- Do NOT include any commentary outside the article blocks.

VOICE GUIDE:
---
{voice}
---

SOURCE METADATA:
- source_id: {source_id}
- entry_id: {entry_id}
- source_hash: {source_hash}
- source_url: {source_url}
- compiled_at: {compiled_at}

SOURCE TEXT:
---
{text}
---
"""


def _build_compiler_agent() -> Agent:
    return Agent(
        id="compile-runner",
        name="Compile Runner",
        model=Claude(id="claude-opus-4-7"),
        instructions="You convert raw documents into Obsidian-compatible markdown articles.",
        markdown=False,
    )


def _split_articles(blob: str) -> list[str]:
    parts = [p.strip() for p in blob.split("===ARTICLE===")]
    return [p for p in parts if p.startswith("---")]


def _extract_title(article: str) -> str:
    for line in article.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


# Required frontmatter keys we always control. The LLM is responsible for
# `tags` and `backlinks`; everything else we stamp ourselves so the
# Linter's "stale article" check (frontmatter source_hash vs scout_compiled
# row) cannot drift due to model error.
_AUTHORITATIVE_KEYS = ("source", "source_url", "source_hash", "compiled_at", "compiled_by", "user_edited")


def _normalize_frontmatter(
    article: str,
    *,
    source_id: str,
    entry_id: str,
    source_url: str | None,
    source_hash: str,
    compiled_at: str,
    needs_split: bool = False,
) -> str:
    """Replace the article's frontmatter with one we control.

    Preserves the LLM's `tags` and `backlinks` if present; overwrites
    everything else. Returns the article text with normalized frontmatter
    + the original body.
    """
    body = article
    tags_line: str | None = None
    backlinks_line: str | None = None

    if article.startswith("---"):
        end = article.find("\n---", 4)
        if end > 0:
            front = article[4:end]
            body = article[end + 4 :].lstrip("\n")
            for raw_line in front.splitlines():
                stripped = raw_line.strip()
                if stripped.startswith("tags:"):
                    tags_line = stripped
                elif stripped.startswith("backlinks:"):
                    backlinks_line = stripped

    src_url_value = source_url if source_url else "null"
    parts = [
        "---",
        f"source: {source_id}:{entry_id}",
        f"source_url: {src_url_value}",
        f"source_hash: {source_hash}",
        f"compiled_at: {compiled_at}",
        f"compiled_by: {COMPILER_VERSION}",
        "user_edited: false",
        f"needs_split: {str(needs_split).lower()}",
    ]
    if tags_line:
        parts.append(tags_line)
    if backlinks_line:
        parts.append(backlinks_line)
    parts.append("---")
    parts.append("")
    parts.append(body)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def compile_entry(
    source: Source,
    entry_id: str,
    *,
    knowledge=None,
    workspace_id: str = WORKSPACE_ID,
    force: bool = False,
) -> CompileResult:
    """Compile a single entry from a source."""
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        content = source.read(entry_id)
    except Exception as e:
        return CompileResult(source.id, entry_id, "error", detail=f"read failed: {e}")

    text = content.text or ""
    if not text.strip():
        return CompileResult(source.id, entry_id, "skipped-empty", detail="no extractable text")

    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    needs_split = len(text) > NEEDS_SPLIT_THRESHOLD
    record = get_record(source.id, entry_id, workspace_id)

    if record and not force and record.source_hash == source_hash:
        return CompileResult(source.id, entry_id, "skipped-unchanged", wiki_path=record.wiki_path)

    # Two-signal user-edit protection (spec §5):
    #  1. Frontmatter `user_edited: true` on disk, OR
    #  2. Disk sha256 of the article ≠ the compiler_output_hash we recorded
    #     when we last wrote it (means the file has been touched since compile).
    if record and _looks_user_edited(record):
        return _compile_and_write(
            source,
            entry_id,
            text,
            content.source_url,
            source_hash,
            knowledge,
            workspace_id,
            needs_split=needs_split,
            sibling_of=record,
        )

    return _compile_and_write(
        source,
        entry_id,
        text,
        content.source_url,
        source_hash,
        knowledge,
        workspace_id,
        needs_split=needs_split,
    )


def _looks_user_edited(record: CompileRecord) -> bool:
    """Two-signal check per §5. Either trips → don't overwrite."""
    wiki_path = Path(record.wiki_path)
    if record.user_edited:
        return True
    if _read_disk_user_edited(wiki_path):
        return True
    if record.compiler_output_hash and wiki_path.exists():
        try:
            current = _sha256_bytes(wiki_path.read_bytes())
        except OSError:
            return False
        if current != record.compiler_output_hash:
            return True
    return False


def _compile_and_write(
    source: Source,
    entry_id: str,
    text: str,
    source_url: str | None,
    source_hash: str,
    knowledge,
    workspace_id: str,
    *,
    needs_split: bool = False,
    sibling_of: CompileRecord | None = None,
) -> CompileResult:
    voice = _voice_guide()
    compiled_at = _now_iso()
    prompt = _COMPILE_INSTRUCTIONS_TMPL.format(
        voice=voice,
        source_id=source.id,
        entry_id=entry_id,
        source_hash=source_hash,
        source_url=source_url or "null",
        compiled_at=compiled_at,
        text=text[:120_000],  # cap absurd inputs
    )
    agent = _build_compiler_agent()
    response = agent.run(prompt)
    blob = (response.content or "").strip()

    articles = _split_articles(blob)
    if not articles:
        return CompileResult(source.id, entry_id, "error", detail="model produced no articles")

    # Per §2 + §5: this build emits exactly one article per raw entry.
    # If the model tries to split, take only the first article and flag
    # the rest for later manual attention via the needs_split surface.
    if len(articles) > 1:
        needs_split = True
        articles = articles[:1]

    written: list[str] = []
    primary_path: Path | None = None
    primary_output_hash: str = ""

    for article in articles:
        article = _normalize_frontmatter(
            article,
            source_id=source.id,
            entry_id=entry_id,
            source_url=source_url,
            source_hash=source_hash,
            compiled_at=compiled_at,
            needs_split=needs_split,
        )
        title = _extract_title(article)
        slug = _slugify(title)
        short = _short_hash(article)
        if sibling_of:
            short = f"{short}-conflict"
        filename = f"{slug}-{short}.md"
        path = ARTICLES_DIR / filename
        file_bytes = (article + "\n").encode("utf-8")
        path.write_bytes(file_bytes)
        written.append(str(path.relative_to(SCOUT_COMPILED_DIR.parent)))
        if primary_path is None:
            primary_path = path
            primary_output_hash = _sha256_bytes(file_bytes)
        if knowledge is not None:
            try:
                knowledge.insert(
                    name=f"Wiki: {title}",
                    text_content=(
                        f"Compiled article at {path.relative_to(SCOUT_COMPILED_DIR.parent)}; "
                        f"compiled from {source.id}:{entry_id}. Tags resolved from frontmatter."
                    ),
                )
            except Exception:
                pass  # never let knowledge write fail the compile

    if primary_path is None:
        return CompileResult(source.id, entry_id, "error", detail="no article written")

    # Linter surface row for oversized raw entries. `Discovery:` is the
    # spec-§8 prefix we're reusing here (tmp/spec-diff.md A3).
    if needs_split and knowledge is not None:
        try:
            knowledge.insert(
                name=f"Discovery: needs_split {primary_path.name}",
                text_content=(
                    f"Source entry {source.id}:{entry_id} exceeded "
                    f"{NEEDS_SPLIT_THRESHOLD} chars. Emitted a single article "
                    f"at {primary_path.relative_to(SCOUT_COMPILED_DIR.parent)}; "
                    "Linter should surface for human follow-up."
                ),
            )
        except Exception:
            pass

    upsert_record(
        CompileRecord(
            source_id=source.id,
            entry_id=entry_id,
            source_hash=source_hash,
            compiler_output_hash=primary_output_hash,
            wiki_path=str(primary_path),
            compiled_at=compiled_at,
            compiled_by=COMPILER_VERSION,
            user_edited=False,
            needs_split=needs_split,
            workspace_id=workspace_id,
        )
    )

    detail = f"wrote {len(written)} article(s)"
    if needs_split:
        detail += f"; needs_split=true (raw {len(text)} chars)"
    if sibling_of:
        detail += f"; sibling of user-edited {sibling_of.wiki_path}"
    return CompileResult(source.id, entry_id, "compiled", wiki_path=str(primary_path), detail=detail)


def compile_source(
    source_id: str,
    *,
    knowledge=None,
    workspace_id: str = WORKSPACE_ID,
    force: bool = False,
    limit: int | None = None,
) -> list[CompileResult]:
    source = get_source(source_id)
    if source is None:
        return [CompileResult(source_id, "", "error", detail="unknown source")]
    if not getattr(source, "compile", False):
        return [CompileResult(source_id, "", "error", detail="source is not compile=True")]

    try:
        entries = source.list()
    except Exception as e:
        return [CompileResult(source_id, "", "error", detail=f"list failed: {e}")]

    results: list[CompileResult] = []
    for i, entry in enumerate(entries):
        if limit is not None and i >= limit:
            break
        results.append(
            compile_entry(source, entry.id, knowledge=knowledge, workspace_id=workspace_id, force=force)
        )
    _refresh_index(workspace_id)
    return results


def compile_all(
    *,
    knowledge=None,
    workspace_id: str = WORKSPACE_ID,
    force: bool = False,
) -> dict[str, list[CompileResult]]:
    out: dict[str, list[CompileResult]] = {}
    for source in get_sources():
        if not getattr(source, "compile", False):
            continue
        out[source.id] = compile_source(
            source.id, knowledge=knowledge, workspace_id=workspace_id, force=force
        )
    return out


# ---------------------------------------------------------------------------
# Index regen — list every article currently on disk
# ---------------------------------------------------------------------------


def _refresh_index(workspace_id: str) -> None:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    SCOUT_COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    articles = sorted(ARTICLES_DIR.glob("*.md"))

    lines = [
        "# Scout Wiki Index",
        "",
        f"_Generated: {_now_iso()}_  ",
        f"_Articles: {len(articles)}_",
        "",
        "## Articles",
        "",
    ]
    for p in articles:
        title = _extract_title(p.read_text(errors="replace"))
        rel = p.relative_to(SCOUT_COMPILED_DIR)
        lines.append(f"- [{title}](compiled/{rel})")

    INDEX_PATH.write_text("\n".join(lines) + "\n")


def index_path() -> Path:
    return INDEX_PATH
