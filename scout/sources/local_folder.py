"""
LocalFolderSource
=================

A folder on disk. Entries are files, recursively. Used in two modes in v3.0:
- `compile=True, live_read=False` for `context/raw/` — user dump zone the
  Compiler iterates over.
- `compile=False, live_read=True` for `context/compiled/` — the Obsidian
  vault, read live by Navigator.

Text extraction is best-effort: PDF via pypdf, docx via python-docx, html
via BeautifulSoup. Plain-text formats (md, txt, json, yaml) read directly.
Binary or unsupported formats return Content with bytes set and text=None;
the Compiler will skip them with a clear log line.

`find` is ripgrep over text content. Lexical only.
"""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scout.sources.base import (
    Capability,
    Content,
    Entry,
    FindKind,
    HealthState,
    HealthStatus,
    Hit,
    Meta,
    NotSupported,
    SourceError,
)

# File extensions we'll attempt to extract text from. Anything else is
# returned as bytes only.
_TEXT_EXTS = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".csv", ".html", ".htm"}
_PDF_EXTS = {".pdf"}
_DOCX_EXTS = {".docx"}
_SKIP_DIRS = {".git", ".obsidian", "node_modules", ".venv", "__pycache__", ".DS_Store"}


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_text(path: Path, raw: bytes) -> str | None:
    """Best-effort extraction. Returns None if format not handled or fails."""
    suffix = path.suffix.lower()
    try:
        if suffix in _TEXT_EXTS:
            text = raw.decode("utf-8", errors="replace")
            if suffix in {".html", ".htm"}:
                try:
                    from bs4 import BeautifulSoup  # type: ignore[import-not-found]

                    return BeautifulSoup(text, "html.parser").get_text(separator="\n")
                except ImportError:
                    return text
            return text
        if suffix in _PDF_EXTS:
            try:
                from io import BytesIO

                from pypdf import PdfReader  # type: ignore[import-not-found]

                reader = PdfReader(BytesIO(raw))
                return "\n\n".join(p.extract_text() or "" for p in reader.pages)
            except ImportError:
                return None
        if suffix in _DOCX_EXTS:
            try:
                from io import BytesIO

                from docx import Document  # type: ignore[import-not-found]

                doc = Document(BytesIO(raw))
                return "\n\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                return None
    except Exception:
        return None
    return None


class LocalFolderSource:
    """A directory-on-disk source. See module docstring for usage."""

    def __init__(
        self,
        path: str | Path,
        *,
        id: str | None = None,
        name: str | None = None,
        compile: bool = False,
        live_read: bool = True,
    ) -> None:
        self.root = Path(path).resolve()
        self.id = id or f"local:{self.root.name}"
        self.name = name or self.root.name
        self.compile = compile
        self.live_read = live_read

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _entry_path(self, entry_id: str) -> Path:
        # entry_id is the path relative to root, slash-normalized
        candidate = (self.root / entry_id).resolve()
        # Prevent directory traversal.
        if self.root not in candidate.parents and candidate != self.root:
            raise SourceError(f"Entry id {entry_id!r} escapes source root")
        return candidate

    def _walk(self, base: Path):
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            yield p

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def list(self, path: str = "") -> list[Entry]:
        base = self._entry_path(path) if path else self.root
        if not base.exists():
            return []
        entries: list[Entry] = []
        for p in self._walk(base):
            stat = p.stat()
            rel = str(p.relative_to(self.root))
            entries.append(
                Entry(
                    id=rel,
                    name=p.name,
                    kind="file",
                    path=rel,
                    size=stat.st_size,
                    modified_at=_iso(stat.st_mtime),
                )
            )
        return entries

    def read(self, entry_id: str) -> Content:
        p = self._entry_path(entry_id)
        if not p.exists() or not p.is_file():
            raise SourceError(f"Entry not found: {entry_id}")
        raw = p.read_bytes()
        text = _extract_text(p, raw)
        mime, _ = mimetypes.guess_type(p.name)
        return Content(
            bytes=raw,
            text=text,
            mime=mime or "application/octet-stream",
            source_url=p.as_uri(),
            citation_hint=str(p.relative_to(self.root)),
        )

    def metadata(self, entry_id: str) -> Meta:
        p = self._entry_path(entry_id)
        if not p.exists():
            raise SourceError(f"Entry not found: {entry_id}")
        stat = p.stat()
        mime, _ = mimetypes.guess_type(p.name)
        return Meta(
            name=p.name,
            mime=mime,
            size=stat.st_size,
            modified_at=_iso(stat.st_mtime),
            source_url=p.as_uri(),
            extra={"path": str(p.relative_to(self.root))},
        )

    def health(self) -> HealthStatus:
        if not self.root.exists():
            return HealthStatus(HealthState.DISCONNECTED, f"{self.root} does not exist")
        if not self.root.is_dir():
            return HealthStatus(HealthState.DISCONNECTED, f"{self.root} is not a directory")
        return HealthStatus(HealthState.CONNECTED, str(self.root))

    def capabilities(self) -> set[Capability]:
        caps = {Capability.LIST, Capability.READ, Capability.METADATA}
        if shutil.which("rg"):
            caps.add(Capability.FIND_LEXICAL)
        return caps

    def find(self, query: str, kind: FindKind = FindKind.LEXICAL) -> list[Hit]:
        if kind != FindKind.LEXICAL:
            raise NotSupported(f"LocalFolderSource only supports lexical find, got {kind}")
        if not shutil.which("rg"):
            # Fall back to a naive Python scan so the source still answers.
            return self._naive_find(query)
        try:
            proc = subprocess.run(
                [
                    "rg",
                    "--no-config",
                    "--no-messages",
                    "-n",
                    "-S",
                    "-m",
                    "5",
                    "-C",
                    "0",
                    "--max-filesize",
                    "5M",
                    query,
                    str(self.root),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return []
        hits: dict[str, Hit] = {}
        for line in proc.stdout.splitlines():
            # ripgrep default: <path>:<lineno>:<text>
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            path_str, lineno, text = parts
            try:
                rel = str(Path(path_str).resolve().relative_to(self.root))
            except ValueError:
                continue
            if rel in hits:
                continue
            hits[rel] = Hit(
                entry_id=rel,
                name=Path(path_str).name,
                score=1.0,
                snippet=f"L{lineno}: {text.strip()[:240]}",
                source_url=Path(path_str).resolve().as_uri(),
                citation_hint=f"{rel}:{lineno}",
            )
            if len(hits) >= 25:
                break
        return list(hits.values())

    def _naive_find(self, query: str) -> list[Hit]:
        needle = query.lower()
        hits: list[Hit] = []
        for p in self._walk(self.root):
            if p.suffix.lower() not in _TEXT_EXTS:
                continue
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            if needle in text.lower():
                idx = text.lower().find(needle)
                snippet = text[max(0, idx - 40) : idx + 200].replace("\n", " ")
                rel = str(p.relative_to(self.root))
                hits.append(
                    Hit(
                        entry_id=rel,
                        name=p.name,
                        score=1.0,
                        snippet=snippet,
                        source_url=p.as_uri(),
                        citation_hint=rel,
                    )
                )
                if len(hits) >= 25:
                    break
        return hits

    # ------------------------------------------------------------------
    # Compile-side helpers (used by the compile runner, not on the protocol)
    # ------------------------------------------------------------------

    def hash_entry(self, entry_id: str) -> str:
        """Stable content hash for compile-state tracking."""
        return _hash_bytes(self._entry_path(entry_id).read_bytes())
