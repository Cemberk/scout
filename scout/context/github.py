"""GithubContext — agentic read-only context over a cloned git repo.

Clones on first health/query into ``$REPOS_DIR/<owner>__<repo>``. The
repo argument is either ``"owner/name"`` shorthand or a full HTTPS URL.
``GITHUB_ACCESS_TOKEN`` is used transparently for private repos.

Read-only: never writes, commits, or pushes.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from os import getenv
from pathlib import Path

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools import tool
from agno.tools.coding import CodingTools

from scout.context.base import Answer, HealthState, HealthStatus

log = logging.getLogger(__name__)


def _repo_dir_name(repo: str) -> str:
    """Normalize an 'owner/name' or URL to a filesystem-safe directory name."""
    cleaned = repo.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://") or cleaned.startswith("git@"):
        stem = cleaned.rsplit("/", 1)[-1]
        return stem[:-4] if stem.endswith(".git") else stem
    return cleaned.replace("/", "__")


def _clone_url(repo: str, token: str) -> str:
    """Build the clone URL. For 'owner/name' shorthand, bake the token
    into the URL if present; full URLs are passed through."""
    if repo.startswith(("http://", "https://", "git@")):
        return repo
    if token:
        return f"https://{token}@github.com/{repo}.git"
    return f"https://github.com/{repo}.git"


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str, str]:
    """Run a command, capture output, return (rc, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


class GithubContext:
    """Agentic context over a cloned GitHub repo."""

    kind: str = "github"

    def __init__(
        self,
        repo: str,
        *,
        branch: str = "main",
        clone_dir: str | None = None,
    ) -> None:
        self.repo = repo
        self.branch = branch
        self.id = f"github:{repo}"
        self.name = repo
        default_root = Path(getenv("REPOS_DIR", ".scout/repos"))
        self.clone_dir = Path(clone_dir) if clone_dir else default_root / _repo_dir_name(repo)
        self._agent: Agent | None = None

    # ------------------------------------------------------------------
    # Health + clone
    # ------------------------------------------------------------------

    def health(self) -> HealthStatus:
        token = getenv("GITHUB_ACCESS_TOKEN", "")
        url = _clone_url(self.repo, token)
        try:
            rc, _, err = _run(["git", "ls-remote", "--heads", url], timeout=20)
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return HealthStatus(HealthState.DISCONNECTED, f"ls-remote failed: {exc}")
        if rc != 0:
            return HealthStatus(HealthState.DISCONNECTED, err.strip() or f"ls-remote rc={rc}")
        return HealthStatus(HealthState.CONNECTED, str(self.clone_dir))

    def _ensure_clone(self) -> Path:
        """Clone on first call; fetch+reset on subsequent calls."""
        token = getenv("GITHUB_ACCESS_TOKEN", "")
        url = _clone_url(self.repo, token)

        if not (self.clone_dir / ".git").exists():
            if self.clone_dir.exists():
                shutil.rmtree(self.clone_dir)
            self.clone_dir.parent.mkdir(parents=True, exist_ok=True)
            rc, _, err = _run(
                ["git", "clone", "--depth", "1", "--branch", self.branch, url, str(self.clone_dir)],
                timeout=300,
            )
            if rc != 0:
                raise RuntimeError(f"git clone failed: {err.strip()}")
        else:
            # Fast-forward to origin/<branch>. Silent on failure — the
            # clone is still usable, just possibly stale.
            _run(["git", "fetch", "origin", self.branch], cwd=self.clone_dir, timeout=60)
            _run(["git", "reset", "--hard", f"origin/{self.branch}"], cwd=self.clone_dir, timeout=60)
        return self.clone_dir

    # ------------------------------------------------------------------
    # Context protocol
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> Answer:
        del filters, limit
        try:
            self._ensure_clone()
        except Exception as exc:
            log.exception("GithubContext.query: clone failed")
            return Answer(text=f"clone failed: {exc}", hits=[])
        agent = self._ensure_agent()
        output = agent.run(question)
        text = output.get_content_as_string() if hasattr(output, "get_content_as_string") else str(output.content)
        return Answer(text=text or "", hits=[])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        return Agent(
            id=f"github-context-{_repo_dir_name(self.repo)}",
            name=f"GithubContext({self.repo})",
            role=f"Read-only exploration of the {self.repo} git repo",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=_instructions(self.repo, self.clone_dir),
            tools=[
                CodingTools(
                    base_dir=self.clone_dir,
                    enable_read_file=True,
                    enable_grep=True,
                    enable_find=True,
                    enable_ls=True,
                    enable_edit_file=False,
                    enable_write_file=False,
                    enable_run_shell=False,
                ),
                *_git_tools(self.clone_dir),
            ],
            markdown=True,
        )


def _git_tools(clone_dir: Path) -> list:
    """Lightweight git helpers scoped to one clone dir."""

    @tool
    def git_log(path: str = "", limit: int = 20) -> str:
        """Recent commits. Pass ``path`` to restrict to a file."""
        args = ["git", "log", f"-n{limit}", "--pretty=format:%h %ad %an %s", "--date=short"]
        if path:
            args.extend(["--", path])
        rc, out, err = _run(args, cwd=clone_dir, timeout=30)
        if rc != 0:
            return json.dumps({"error": err.strip()})
        return out

    @tool
    def git_blame(path: str, line_start: int = 1, line_end: int = 200) -> str:
        """Blame for a range of lines in a file."""
        rc, out, err = _run(
            ["git", "blame", "-L", f"{line_start},{line_end}", path],
            cwd=clone_dir,
            timeout=30,
        )
        if rc != 0:
            return json.dumps({"error": err.strip()})
        return out

    @tool
    def git_diff(ref1: str = "HEAD~1", ref2: str = "HEAD", path: str = "") -> str:
        """Diff between two refs. Pass ``path`` to restrict."""
        args = ["git", "diff", ref1, ref2]
        if path:
            args.extend(["--", path])
        rc, out, err = _run(args, cwd=clone_dir, timeout=30)
        if rc != 0:
            return json.dumps({"error": err.strip()})
        return out[:50_000]  # cap huge diffs

    @tool
    def git_show(ref: str) -> str:
        """Show a commit's message + diff."""
        rc, out, err = _run(["git", "show", ref], cwd=clone_dir, timeout=30)
        if rc != 0:
            return json.dumps({"error": err.strip()})
        return out[:50_000]

    return [git_log, git_blame, git_diff, git_show]


def _instructions(repo: str, clone_dir: Path) -> str:
    return f"""\
You are a read-only explorer of the git repo `{repo}`, cloned at `{clone_dir}`.

Answer questions by:
- `list_dir` to see structure
- `grep` to search for keywords
- `read_file` to fetch specific files
- `git_log` / `git_blame` / `git_diff` / `git_show` for history

Cite `path:line` in your answer. Keep responses concise. If you find
nothing relevant, say so explicitly with what you searched. Never
output .env contents, API keys, tokens, passwords, or secrets; if you
encounter them during exploration, stop and report the path only.
"""
