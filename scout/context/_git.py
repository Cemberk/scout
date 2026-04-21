"""Shared git helpers used by GithubContextProvider and GithubWikiBackend.

Factored here so the clone-url + run + repo-dir-name logic doesn't
diverge between read-only exploration (``GithubContextProvider``) and
read/write-via-commit (``GithubWikiBackend``).
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

    Safety: if ``clone_dir`` exists but has no ``.git``, we'd normally
    rmtree it so the clone can start clean — but a misconfigured
    ``REPOS_DIR`` (e.g. pointing at the user's home directory) would
    then wipe real content. Refuse unless the dir is empty or its name
    looks like a Scout-owned clone (either ``<owner>__<repo>`` or
    ``_wiki`` for the wiki backend).
    """
    url = clone_url(repo, token)
    if not (clone_dir / ".git").exists():
        if clone_dir.exists():
            if not _is_safe_to_rmtree(clone_dir):
                raise RuntimeError(
                    f"refusing to clear {clone_dir}: existing content doesn't look Scout-owned. "
                    "Fix REPOS_DIR, or remove the directory by hand if this is intentional."
                )
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


def _is_safe_to_rmtree(path: Path) -> bool:
    """True if ``path`` is empty or recognizably Scout-owned.

    Scout clone-dir names are either ``<owner>__<repo>`` (dunder from
    ``repo_dir_name``) or ``_wiki/<owner>__<repo>`` for the wiki backend.
    Anything else — a user's home dir, a random repo they cloned by hand
    — is refused.
    """
    try:
        if not any(path.iterdir()):
            return True
    except OSError:
        return False
    name = path.name
    parent = path.parent.name
    return "__" in name or parent == "_wiki"
