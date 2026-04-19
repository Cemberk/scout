"""WikiContext — the one compile-capable knowledge store.

Implements the Context protocol (query + health) and adds ingest + compile.
Holds a WikiBackend which handles raw-bytes I/O against the substrate
(local filesystem, git repo, or S3 bucket).

Layout managed on the backend:
- ``raw/<slug>-<short-sha>.md``   — ingested content
- ``compiled/<slug>-<hash>.md``   — compiled articles
- ``.scout/state.json``           — per-entry compile state

Single instance per Scout. Configured via ``SCOUT_WIKI`` env.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools import tool

from scout.context.base import Answer, Entry, HealthStatus, Hit

if TYPE_CHECKING:
    from scout.context.base import WikiBackend

log = logging.getLogger(__name__)

STATE_PATH = ".scout/state.json"
RAW_PREFIX = "raw/"
COMPILED_PREFIX = "compiled/"

# Oversized raw entries still emit a single article; flagged with
# needs_split=true in the state row.
NEEDS_SPLIT_THRESHOLD = 20_000


# ----------------------------------------------------------------------
# Compile state — JSON on the backend, not Postgres.
# ----------------------------------------------------------------------


@dataclass
class StateEntry:
    entry_id: str
    source_hash: str
    compiled_path: str
    compiled_at: str
    needs_split: bool = False


@dataclass
class WikiState:
    entries: list[StateEntry] = field(default_factory=list)

    def get(self, entry_id: str) -> StateEntry | None:
        for e in self.entries:
            if e.entry_id == entry_id:
                return e
        return None

    def upsert(self, entry: StateEntry) -> None:
        for i, existing in enumerate(self.entries):
            if existing.entry_id == entry.entry_id:
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def remove(self, entry_id: str) -> None:
        self.entries = [e for e in self.entries if e.entry_id != entry_id]

    def to_json(self) -> str:
        return json.dumps(
            {"entries": [e.__dict__ for e in self.entries]},
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> WikiState:
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return cls()
        entries = [StateEntry(**row) for row in data.get("entries", [])]
        return cls(entries=entries)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")[:60] or "article"


def _short_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    segment = (parsed.path or "").rsplit("/", 1)[-1] or parsed.netloc
    stem = segment.split("?")[0].rsplit(".", 1)[0]
    return _slugify(stem)


def _build_raw_frontmatter(title: str, source: str, tags: list[str] | None) -> str:
    tag_str = ", ".join(tags or [])
    return (
        f"---\n"
        f'title: "{title}"\n'
        f"source: {source}\n"
        f"fetched_at: {_now_iso()}\n"
        f"tags: [{tag_str}]\n"
        f"---\n\n"
    )


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


# ----------------------------------------------------------------------
# Compile prompt (self-contained; no runner.py port)
# ----------------------------------------------------------------------


_COMPILE_INSTRUCTIONS_TMPL = """\
You are the Scout Compiler. Convert the SOURCE below into a single
Obsidian-compatible markdown article following the voice guide.

Output rules:
- One article only. Start with full YAML frontmatter.
- Frontmatter keys: title, tags (2–5 lowercase kebab-case, YAML list),
  backlinks (1–4 likely sibling articles, YAML list of `[[slug]]`).
- Omit source / source_url / source_hash / compiled_at — the wiki
  stamps those itself after your reply.
- Body starts with `# <title>` then the content. No commentary outside
  the article.

Fidelity:
- Preserve every enumerated item. Tighten prose per item, don't drop
  items.
- Preserve owners, dates, numbers, and proper nouns verbatim.
- Mirror the source's structure as H2 sections when it's obvious.

VOICE GUIDE:
---
{voice}
---

SOURCE METADATA:
- entry_id: {entry_id}
- source_hash: {source_hash}
- fetched_at: {fetched_at}

SOURCE TEXT:
---
{text}
---
"""


# ----------------------------------------------------------------------
# WikiContext
# ----------------------------------------------------------------------


class WikiContext:
    """The one compile-capable knowledge store. Configured via SCOUT_WIKI."""

    id: str = "wiki"
    name: str = "Wiki"
    kind: str = "wiki"

    def __init__(self, backend: WikiBackend) -> None:
        self.backend = backend
        self._query_agent: Agent | None = None

    # ------------------------------------------------------------------
    # Context protocol
    # ------------------------------------------------------------------

    def health(self) -> HealthStatus:
        return self.backend.health()

    def query(
        self,
        question: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> Answer:
        del filters, limit
        agent = self._ensure_query_agent()
        output = agent.run(question)
        text = output.get_content_as_string() if hasattr(output, "get_content_as_string") else str(output.content)
        return Answer(text=text or "", hits=[])

    # ------------------------------------------------------------------
    # Ingest — writes into raw/ via the backend.
    # ------------------------------------------------------------------

    def ingest_url(self, url: str, *, title: str, tags: list[str] | None = None) -> Entry:
        """Fetch a URL, extract text, write under raw/."""
        body = self._fetch_url(url)
        display_title = title or _slug_from_url(url).replace("-", " ").title() or url
        return self._write_raw(display_title, body, source=url, tags=tags)

    def ingest_text(self, text: str, *, title: str, tags: list[str] | None = None) -> Entry:
        """Write text under raw/."""
        if not title:
            raise ValueError("title is required for ingest_text")
        return self._write_raw(title, text or "", source="user", tags=tags)

    def _fetch_url(self, url: str) -> str:
        """Fetch + extract. Uses Parallel when PARALLEL_API_KEY is set;
        otherwise returns a stub body pointing at the URL."""
        # Import at call-time so a missing optional dep never breaks the wiki.
        try:
            from scout.settings import PARALLEL_API_KEY
        except Exception:
            PARALLEL_API_KEY = ""  # type: ignore[assignment]

        if PARALLEL_API_KEY:
            try:
                from parallel import Parallel  # type: ignore[import-not-found]

                client = Parallel(api_key=PARALLEL_API_KEY)
                result = client.beta.extract(urls=[url], full_content=True)
                if result and result.results:
                    r = result.results[0]
                    return r.full_content or ""
            except Exception as exc:
                log.warning("wiki.ingest_url: extraction failed for %s: %s", url, exc)
        return f"Source: {url}\n\n*(Content pending — configure PARALLEL_API_KEY or use ingest_text.)*"

    def _write_raw(self, title: str, body: str, *, source: str, tags: list[str] | None) -> Entry:
        slug = _slugify(title)
        short = _short_hash(body.encode("utf-8"))
        path = f"{RAW_PREFIX}{slug}-{short}.md"

        # Idempotency: same body → same short hash → already there. Don't
        # touch the backend.
        for existing in self.backend.list_paths(RAW_PREFIX):
            if existing.endswith(f"-{short}.md"):
                return Entry(id=existing, name=title, kind="raw", path=existing)

        frontmatter = _build_raw_frontmatter(title, source, tags)
        self.backend.write_bytes(path, (frontmatter + body + "\n").encode("utf-8"))
        return Entry(id=path, name=title, kind="raw", path=path)

    # ------------------------------------------------------------------
    # Compile — iterate raw/, diff vs state, LLM-transform, write compiled/.
    # ------------------------------------------------------------------

    def compile(self, *, force: bool = False) -> dict:
        """Run one compile pass. Returns counts keyed by outcome."""
        state = self._load_state()
        raw_paths = [p for p in self.backend.list_paths(RAW_PREFIX) if p.endswith(".md")]

        counts: dict[str, int] = {"compiled": 0, "skipped-unchanged": 0, "skipped-empty": 0, "pruned": 0, "error": 0}
        seen: set[str] = set()

        for raw_path in raw_paths:
            seen.add(raw_path)
            try:
                raw_bytes = self.backend.read_bytes(raw_path)
            except Exception as exc:
                log.warning("wiki.compile: read failed for %s: %s", raw_path, exc)
                counts["error"] += 1
                continue

            text = raw_bytes.decode("utf-8", errors="replace")
            if not text.strip():
                counts["skipped-empty"] += 1
                continue

            source_hash = _sha256(raw_bytes)
            existing = state.get(raw_path)
            if existing and not force and existing.source_hash == source_hash:
                counts["skipped-unchanged"] += 1
                continue

            result = self._compile_one(raw_path, text, source_hash)
            if result is None:
                counts["error"] += 1
                continue

            compiled_path, needs_split = result
            # Delete the prior compiled file if the filename rotated.
            if existing and existing.compiled_path and existing.compiled_path != compiled_path:
                try:
                    self.backend.delete(existing.compiled_path)
                except Exception:
                    pass

            state.upsert(
                StateEntry(
                    entry_id=raw_path,
                    source_hash=source_hash,
                    compiled_path=compiled_path,
                    compiled_at=_now_iso(),
                    needs_split=needs_split,
                )
            )
            counts["compiled"] += 1

        # Prune orphans: state rows whose raw/ entry is gone.
        for orphan in [e for e in state.entries if e.entry_id not in seen]:
            try:
                if orphan.compiled_path:
                    self.backend.delete(orphan.compiled_path)
            except Exception:
                pass
            state.remove(orphan.entry_id)
            counts["pruned"] += 1

        self._save_state(state)
        return counts

    def _compile_one(self, raw_path: str, text: str, source_hash: str) -> tuple[str, bool] | None:
        """LLM-transform one raw entry. Returns (compiled_path, needs_split)."""
        needs_split = len(text) > NEEDS_SPLIT_THRESHOLD
        voice = self._voice_guide()
        prompt = _COMPILE_INSTRUCTIONS_TMPL.format(
            voice=voice,
            entry_id=raw_path,
            source_hash=source_hash,
            fetched_at=_now_iso(),
            text=text[:120_000],
        )
        agent = self._build_compiler_agent()
        response = agent.run(prompt)
        article = (response.content or "").strip()
        if not article.startswith("---"):
            log.warning("wiki.compile: model output for %s had no frontmatter", raw_path)
            return None

        # Stamp authoritative frontmatter keys.
        article = self._stamp_frontmatter(
            article,
            entry_id=raw_path,
            source_hash=source_hash,
            needs_split=needs_split,
        )
        title = _extract_title(article)
        slug = _slugify(title)
        file_bytes = (article + "\n").encode("utf-8")
        short = _short_hash(file_bytes)
        compiled_path = f"{COMPILED_PREFIX}{slug}-{short}.md"
        self.backend.write_bytes(compiled_path, file_bytes)
        return compiled_path, needs_split

    def _stamp_frontmatter(
        self,
        article: str,
        *,
        entry_id: str,
        source_hash: str,
        needs_split: bool,
    ) -> str:
        """Inject source / source_hash / compiled_at / user_edited / needs_split
        into the LLM's frontmatter. Preserves model-authored tags + backlinks."""
        end = article.find("\n---", 4)
        if end < 0:
            return article
        front = article[4:end]
        body = article[end + 4 :].lstrip("\n")

        tags_line: str | None = None
        backlinks_line: str | None = None
        title_line: str | None = None
        for raw_line in front.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("tags:"):
                tags_line = stripped
            elif stripped.startswith("backlinks:"):
                backlinks_line = stripped
            elif stripped.startswith("title:"):
                title_line = stripped

        parts = ["---"]
        if title_line:
            parts.append(title_line)
        parts.extend(
            [
                f"source: {entry_id}",
                f"source_hash: {source_hash}",
                f"compiled_at: {_now_iso()}",
                "user_edited: false",
                f"needs_split: {str(needs_split).lower()}",
            ]
        )
        if tags_line:
            parts.append(tags_line)
        if backlinks_line:
            parts.append(backlinks_line)
        parts.append("---")
        parts.append("")
        parts.append(body)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_state(self) -> WikiState:
        try:
            raw = self.backend.read_bytes(STATE_PATH)
        except Exception:
            return WikiState()
        return WikiState.from_json(raw.decode("utf-8", errors="replace"))

    def _save_state(self, state: WikiState) -> None:
        self.backend.write_bytes(STATE_PATH, state.to_json().encode("utf-8"))

    def _voice_guide(self) -> str:
        try:
            from scout.settings import CONTEXT_VOICE_DIR

            p = CONTEXT_VOICE_DIR / "wiki-article.md"
            if p.exists():
                return p.read_text()
        except Exception:
            pass
        return ""

    def _build_compiler_agent(self) -> Agent:
        return Agent(
            id="wiki-compiler",
            name="Wiki Compiler",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions="You convert raw documents into Obsidian-compatible markdown articles.",
            markdown=False,
        )

    def _ensure_query_agent(self) -> Agent:
        if self._query_agent is None:
            self._query_agent = self._build_query_agent()
        return self._query_agent

    def _build_query_agent(self) -> Agent:
        """Agent with backend-wrapped read tools over compiled/ and raw/."""
        backend = self.backend

        @tool
        def list_compiled() -> str:
            """List every compiled article path in the wiki."""
            paths = [p for p in backend.list_paths(COMPILED_PREFIX) if p.endswith(".md")]
            return json.dumps({"paths": paths})

        @tool
        def list_raw() -> str:
            """List every raw (not-yet-compiled) entry path."""
            paths = [p for p in backend.list_paths(RAW_PREFIX) if p.endswith(".md")]
            return json.dumps({"paths": paths})

        @tool
        def read_article(path: str) -> str:
            """Read a compiled article or raw entry by path."""
            try:
                data = backend.read_bytes(path)
            except Exception as exc:
                return json.dumps({"error": str(exc)})
            return data.decode("utf-8", errors="replace")

        @tool
        def search_wiki(needle: str) -> str:
            """Substring search across every compiled article. Returns matching paths."""
            hits: list[dict[str, Any]] = []
            needle_lower = needle.lower()
            for path in backend.list_paths(COMPILED_PREFIX):
                if not path.endswith(".md"):
                    continue
                try:
                    text = backend.read_bytes(path).decode("utf-8", errors="replace")
                except Exception:
                    continue
                if needle_lower in text.lower():
                    idx = text.lower().find(needle_lower)
                    snippet = text[max(0, idx - 60) : idx + 200].replace("\n", " ")
                    hits.append({"path": path, "snippet": snippet})
                    if len(hits) >= 20:
                        break
            return json.dumps({"hits": hits})

        return Agent(
            id="wiki-query",
            name="Wiki Query",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=(
                "You answer questions from the Scout wiki. Use search_wiki to "
                "locate relevant articles, then read_article on each hit. Cite "
                "the path of every article you used. If compiled/ has nothing, "
                "fall back to list_raw + read_article. If nothing matches, say so."
            ),
            tools=[list_compiled, list_raw, read_article, search_wiki],
            markdown=True,
        )


__all__ = ["WikiContext", "Hit"]
