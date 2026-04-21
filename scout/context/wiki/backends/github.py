"""GithubWikiBackend — WikiBackend that commits + pushes to a GitHub repo.

Operates on a local clone (full history — ``shallow=False`` — so rebase
works). Every ``write_bytes`` / ``delete`` commits one file and pushes;
on push rejection, pulls --rebase and retries up to 3 times. This is the
concurrency story: git coordinates, not Scout.
"""

from __future__ import annotations

import logging
import time
from os import getenv
from pathlib import Path

from scout.context._git import clone_url, ensure_clone, repo_dir_name, run
from scout.context.base import HealthState, HealthStatus

log = logging.getLogger(__name__)

_PUSH_RETRIES = 3


class GithubWikiBackend:
    """WikiBackend whose substrate is a GitHub repo."""

    kind: str = "github"

    def __init__(
        self,
        repo: str,
        *,
        branch: str = "main",
        token_env: str = "GITHUB_ACCESS_TOKEN",
        clone_dir: str | None = None,
    ) -> None:
        self.repo = repo
        self.branch = branch
        self.token_env = token_env
        default_root = Path(getenv("REPOS_DIR", ".scout/repos")) / "_wiki"
        self.clone_dir = Path(clone_dir) if clone_dir else default_root / repo_dir_name(repo)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> HealthStatus:
        token = getenv(self.token_env, "")
        url = clone_url(self.repo, token)
        try:
            rc, _, err = run(["git", "ls-remote", "--heads", url], timeout=20)
        except Exception as exc:
            return HealthStatus(HealthState.DISCONNECTED, f"ls-remote failed: {exc}")
        if rc != 0:
            return HealthStatus(HealthState.DISCONNECTED, err.strip() or f"ls-remote rc={rc}")
        return HealthStatus(HealthState.CONNECTED, str(self.clone_dir))

    # ------------------------------------------------------------------
    # WikiBackend protocol
    # ------------------------------------------------------------------

    def list_paths(self, prefix: str = "") -> list[str]:
        self._ensure_clone()
        base = self._resolve(prefix) if prefix else self.clone_dir
        if not base.exists():
            return []
        out: list[str] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part == ".git" for part in p.parts):
                continue
            try:
                rel = p.relative_to(self.clone_dir)
            except ValueError:
                continue
            out.append(str(rel))
        return sorted(out)

    def read_bytes(self, path: str) -> bytes:
        self._ensure_clone()
        return self._resolve(path).read_bytes()

    def write_bytes(self, path: str, content: bytes) -> None:
        self._ensure_clone()
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        self._commit_push(path, message=f"scout: update {path}")

    def delete(self, path: str) -> None:
        self._ensure_clone()
        target = self._resolve(path)
        if not target.exists():
            return
        target.unlink()
        self._commit_push(path, message=f"scout: delete {path}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_clone(self) -> None:
        token = getenv(self.token_env, "")
        # Full history so git-rebase works on push rejection.
        ensure_clone(self.repo, self.clone_dir, self.branch, token, shallow=False)
        self._configure_commit_identity()

    def _configure_commit_identity(self) -> None:
        """Idempotent — sets a bot identity on the local clone so commits
        don't fail for lack of user.email / user.name."""
        run(["git", "config", "user.email", "scout@agno.local"], cwd=self.clone_dir, timeout=10)
        run(["git", "config", "user.name", "Scout"], cwd=self.clone_dir, timeout=10)

    def _commit_push(self, path: str, *, message: str) -> None:
        """Commit the single file at ``path`` and push, retrying on conflict."""
        rc_add, _, err_add = run(["git", "add", "--", path], cwd=self.clone_dir, timeout=30)
        if rc_add != 0:
            raise RuntimeError(f"git add failed: {err_add.strip()}")

        # If nothing staged (no actual change), short-circuit.
        rc_diff, out_diff, _ = run(["git", "diff", "--cached", "--quiet"], cwd=self.clone_dir, timeout=10)
        # git diff --quiet returns 0 if no diff, 1 if diff present.
        if rc_diff == 0:
            log.debug("GithubWikiBackend: nothing staged for %s; skipping commit", path)
            return

        rc_commit, _, err_commit = run(["git", "commit", "-m", message], cwd=self.clone_dir, timeout=30)
        if rc_commit != 0:
            raise RuntimeError(f"git commit failed: {err_commit.strip()}")

        for attempt in range(1, _PUSH_RETRIES + 1):
            rc_push, _, err_push = run(
                ["git", "push", "origin", self.branch],
                cwd=self.clone_dir,
                timeout=60,
            )
            if rc_push == 0:
                return
            log.warning(
                "GithubWikiBackend: push rejected (attempt %d/%d): %s",
                attempt,
                _PUSH_RETRIES,
                err_push.strip(),
            )
            rc_pull, _, err_pull = run(
                ["git", "pull", "--rebase", "origin", self.branch],
                cwd=self.clone_dir,
                timeout=60,
            )
            if rc_pull != 0:
                raise RuntimeError(f"git pull --rebase failed: {err_pull.strip()}")
            # small jittered backoff so two concurrent writers don't lock-step
            time.sleep(0.3 * attempt)

        raise RuntimeError(f"git push failed after {_PUSH_RETRIES} retries")

    def _resolve(self, path: str) -> Path:
        """Normalize and guard against escapes out of the clone."""
        target = (self.clone_dir / path).resolve()
        try:
            target.relative_to(self.clone_dir.resolve())
        except ValueError:
            raise ValueError(f"path {path!r} escapes backend clone {self.clone_dir}") from None
        return target
