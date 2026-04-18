"""
GitHubSource
============

Live-read source over a small set of GitHub repos. Per spec §4.4.

Each configured repo is shallow-cloned under `./.scout-cache/repos/<owner>-<repo>/`
on first `health()` call (or first `list`/`read`/`find` that needs the tree).
Repos are refreshed with `git fetch --depth=1` opportunistically, debounced.

- `list(path="")` → one Entry(kind=folder) per configured repo.
- `list("<owner>/<repo>[/subpath]")` → walks the working tree.
- `read("<owner>/<repo>/<path>")` → file read from the local clone.
- `find(kind=LEXICAL)` → ripgrep across all clones. Sequential per repo,
  30s per-repo timeout, cap 25 hits total (see tmp/spec-diff.md A6).
- `find(kind=NATIVE)` → GitHub REST `search/code`. Used for ad-hoc
  public repos not in the configured list.
- `health` → `gh api /rate_limit` via httpx. `UNCONFIGURED` if no
  `GITHUB_REPOS` — token is optional (public repos work anonymously
  at a lower rate ceiling; REST `search/code` stays off without it).
- capabilities: LIST, READ, METADATA, FIND_LEXICAL, FIND_NATIVE.

Read-only everywhere — no push, no PR tools exposed.
"""

from __future__ import annotations

import mimetypes
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable

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

# Alias builtins.list — the class body below defines `def list`, which shadows
# `list` in class scope and breaks mypy on `-> list[...]` return annotations.
_list = list

_CACHE_ROOT = Path(".scout-cache/repos").resolve()
_FETCH_DEBOUNCE_S = 300  # 5 min
_RG_PER_REPO_TIMEOUT = 30
_MAX_HITS = 25
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}


def _slug(owner_repo: str) -> str:
    return owner_repo.replace("/", "-")


class GitHubSource:
    """Live-read GitHub, backed by local clones + REST `search/code`."""

    def __init__(
        self,
        repos: Iterable[str],
        token: str,
        *,
        id: str = "github",
        name: str = "GitHub",
        compile: bool = False,
        live_read: bool = True,
    ) -> None:
        self.repos = tuple(repos)  # ["owner/repo", ...]
        self.token = token
        self.id = id
        self.name = name
        self.compile = compile
        self.live_read = live_read
        self._last_fetch: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Clone management
    # ------------------------------------------------------------------

    def _clone_dir(self, owner_repo: str) -> Path:
        return _CACHE_ROOT / _slug(owner_repo)

    def _ensure_clone(self, owner_repo: str) -> Path:
        target = self._clone_dir(owner_repo)
        if target.exists() and (target / ".git").exists():
            self._maybe_fetch(owner_repo, target)
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        url = (
            f"https://{self.token}@github.com/{owner_repo}.git"
            if self.token
            else f"https://github.com/{owner_repo}.git"
        )
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", url, str(target)],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as e:
            raise SourceError(f"clone of {owner_repo} timed out") from e
        except subprocess.CalledProcessError as e:
            # Strip the token from any error message.
            msg = (e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e))[:240]
            if self.token:
                msg = msg.replace(self.token, "<token>")
            raise SourceError(f"clone of {owner_repo} failed: {msg}") from e
        self._last_fetch[owner_repo] = time.monotonic()
        return target

    def _maybe_fetch(self, owner_repo: str, target: Path) -> None:
        now = time.monotonic()
        last = self._last_fetch.get(owner_repo, 0.0)
        if now - last < _FETCH_DEBOUNCE_S:
            return
        try:
            subprocess.run(
                ["git", "fetch", "--depth=1", "origin"],
                cwd=str(target),
                capture_output=True,
                timeout=60,
            )
        except Exception:
            pass  # stay on current snapshot
        self._last_fetch[owner_repo] = now

    def _entry_for_repo(self, owner_repo: str) -> Path:
        if owner_repo not in self.repos:
            raise SourceError(f"{owner_repo} is not in GITHUB_REPOS")
        return self._ensure_clone(owner_repo)

    def _split_entry_id(self, entry_id: str) -> tuple[str, str]:
        """`owner/repo/subpath` → ('owner/repo', 'subpath')."""
        parts = entry_id.split("/", 2)
        if len(parts) < 2:
            raise SourceError(f"entry_id must be 'owner/repo[/path]', got {entry_id!r}")
        owner_repo = f"{parts[0]}/{parts[1]}"
        subpath = parts[2] if len(parts) == 3 else ""
        return owner_repo, subpath

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def list(self, path: str = "") -> _list[Entry]:
        if not path:
            return [Entry(id=repo, name=repo, kind="folder", path=repo) for repo in self.repos]
        owner_repo, subpath = self._split_entry_id(path)
        clone = self._entry_for_repo(owner_repo)
        base = (clone / subpath).resolve() if subpath else clone
        if clone.resolve() not in base.parents and base != clone.resolve():
            raise SourceError(f"path {path!r} escapes {owner_repo} clone")
        if not base.exists():
            return []
        entries: list[Entry] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            rel = p.relative_to(clone)
            entries.append(
                Entry(
                    id=f"{owner_repo}/{rel}",
                    name=p.name,
                    kind="file",
                    path=f"{owner_repo}/{rel}",
                    size=p.stat().st_size,
                )
            )
        return entries

    def read(self, entry_id: str) -> Content:
        owner_repo, subpath = self._split_entry_id(entry_id)
        if not subpath:
            raise SourceError("read requires a file path inside the repo")
        clone = self._entry_for_repo(owner_repo)
        target = (clone / subpath).resolve()
        if clone.resolve() not in target.parents:
            raise SourceError(f"entry {entry_id!r} escapes clone")
        if not target.exists() or not target.is_file():
            raise SourceError(f"entry not found: {entry_id}")
        raw = target.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        mime, _ = mimetypes.guess_type(target.name)
        return Content(
            bytes=raw,
            text=text,
            mime=mime or "application/octet-stream",
            source_url=f"https://github.com/{owner_repo}/blob/HEAD/{subpath}",
            citation_hint=f"{owner_repo}:{subpath}",
        )

    def metadata(self, entry_id: str) -> Meta:
        owner_repo, subpath = self._split_entry_id(entry_id)
        clone = self._entry_for_repo(owner_repo)
        target = (clone / subpath).resolve() if subpath else clone
        if not target.exists():
            raise SourceError(f"entry not found: {entry_id}")
        stat = target.stat()
        mime, _ = mimetypes.guess_type(target.name) if subpath else (None, None)
        return Meta(
            name=target.name,
            mime=mime,
            size=stat.st_size if target.is_file() else None,
            source_url=f"https://github.com/{owner_repo}" + (f"/blob/HEAD/{subpath}" if subpath else ""),
            extra={"owner_repo": owner_repo, "path": subpath},
        )

    def health(self) -> HealthStatus:
        if not self.repos:
            return HealthStatus(HealthState.UNCONFIGURED, "GITHUB_REPOS not set")
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError:
            return HealthStatus(HealthState.UNCONFIGURED, "httpx not installed")
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            resp = httpx.get(
                "https://api.github.com/rate_limit",
                headers=headers,
                timeout=10.0,
            )
        except Exception as e:
            return HealthStatus(HealthState.DEGRADED, str(e)[:160])
        if resp.status_code >= 400:
            return HealthStatus(HealthState.DEGRADED, f"status {resp.status_code}")
        data = resp.json().get("resources", {}).get("core", {})
        remaining = data.get("remaining", "?")
        mode = "authed" if self.token else "anon"
        return HealthStatus(HealthState.CONNECTED, f"{len(self.repos)} repo(s), {mode}, rate={remaining}")

    def capabilities(self) -> set[Capability]:
        return {
            Capability.LIST,
            Capability.READ,
            Capability.METADATA,
            Capability.FIND_LEXICAL,
            Capability.FIND_NATIVE,
        }

    def find(self, query: str, kind: FindKind = FindKind.LEXICAL) -> _list[Hit]:
        if kind == FindKind.LEXICAL:
            return self._find_lexical(query)
        if kind == FindKind.NATIVE:
            return self._find_native(query)
        raise NotSupported(f"GitHubSource does not support {kind}")

    # ------------------------------------------------------------------
    # Find implementations
    # ------------------------------------------------------------------

    def _find_lexical(self, query: str) -> _list[Hit]:
        if not shutil.which("rg"):
            return []
        hits: list[Hit] = []
        for owner_repo in self.repos:
            if len(hits) >= _MAX_HITS:
                break
            try:
                clone = self._entry_for_repo(owner_repo)
            except SourceError:
                continue
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
                        str(clone),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=_RG_PER_REPO_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                continue
            for line in proc.stdout.splitlines():
                if len(hits) >= _MAX_HITS:
                    break
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                path_str, lineno, body = parts
                try:
                    rel = Path(path_str).resolve().relative_to(clone)
                except ValueError:
                    continue
                hits.append(
                    Hit(
                        entry_id=f"{owner_repo}/{rel}",
                        name=Path(path_str).name,
                        score=1.0,
                        snippet=f"L{lineno}: {body.strip()[:240]}",
                        source_url=f"https://github.com/{owner_repo}/blob/HEAD/{rel}#L{lineno}",
                        citation_hint=f"{owner_repo}:{rel}:{lineno}",
                    )
                )
        return hits

    def _find_native(self, query: str) -> _list[Hit]:
        """GitHub REST search/code. Used for ad-hoc public repos only."""
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError:
            return []
        if not self.token:
            return []
        try:
            resp = httpx.get(
                "https://api.github.com/search/code",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github.text-match+json",
                },
                params={"q": query, "per_page": _MAX_HITS},
                timeout=10.0,
            )
        except Exception as e:
            raise SourceError(f"github search failed: {e}") from e
        if resp.status_code >= 400:
            return []
        hits: list[Hit] = []
        for item in resp.json().get("items", [])[:_MAX_HITS]:
            repo_full = (item.get("repository") or {}).get("full_name", "")
            path = item.get("path", "")
            hits.append(
                Hit(
                    entry_id=f"{repo_full}/{path}" if repo_full else path,
                    name=item.get("name", path),
                    score=float(item.get("score") or 1.0),
                    snippet=(item.get("text_matches") or [{}])[0].get("fragment"),
                    source_url=item.get("html_url"),
                    citation_hint=f"{repo_full}:{path}" if repo_full else path,
                )
            )
        return hits
