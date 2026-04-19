"""Shared git helpers used by GithubContext and GithubBackend.

Factored here so the clone-url + run + repo-dir-name logic doesn't
diverge between read-only exploration (GithubContext) and
read/write-via-commit (GithubBackend).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def repo_dir_name(repo: str) -> str:
    """Normalize an 'owner/name' or URL to a filesystem-safe dir name."""
    cleaned = repo.strip()
    if cleaned.startswith(("http://", "https://", "git@")):
        stem = cleaned.rsplit("/", 1)[-1]
        return stem[:-4] if stem.endswith(".git") else stem
    return cleaned.replace("/", "__")


def clone_url(repo: str, token: str) -> str:
    """Build the clone URL. 'owner/name' → https://github.com/owner/name.git,
    with the token baked in when present. Full URLs are passed through."""
    if repo.startswith(("http://", "https://", "git@")):
        return repo
    if token:
        return f"https://{token}@github.com/{repo}.git"
    return f"https://github.com/{repo}.git"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str, str]:
    """Run a command; return (rc, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def ensure_clone(
    repo: str,
    clone_dir: Path,
    branch: str,
    token: str,
    *,
    shallow: bool = True,
) -> None:
    """Clone on first call; fetch + hard-reset on subsequent calls.

    ``shallow=True`` is appropriate for read-only exploration; backends
    that commit back need full history (``shallow=False``).
    """
    url = clone_url(repo, token)
    if not (clone_dir / ".git").exists():
        if clone_dir.exists():
            shutil.rmtree(clone_dir)
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        args = ["git", "clone"]
        if shallow:
            args.extend(["--depth", "1"])
        args.extend(["--branch", branch, url, str(clone_dir)])
        rc, _, err = run(args, timeout=300)
        if rc != 0:
            raise RuntimeError(f"git clone failed: {err.strip()}")
        return
    run(["git", "fetch", "origin", branch], cwd=clone_dir, timeout=60)
    run(["git", "reset", "--hard", f"origin/{branch}"], cwd=clone_dir, timeout=60)
