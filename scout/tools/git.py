"""Git tools for on-demand repository cloning and read-only inspection.

Scout's CodeExplorer agent uses this toolkit to clone an arbitrary git
repo on demand and read from it. There is no pre-configured repo list,
no worktree lifecycle, and no push. All operations are read-only or
idempotent (clone-or-pull).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from agno.tools import Toolkit
from agno.utils.log import logger


class GitTools(Toolkit):
    """Read-only git toolkit with an on-demand `clone_repo` helper.

    All paths are validated to stay within `base_dir` (the ephemeral
    scratch directory for the session).
    """

    def __init__(self, base_dir: str = "/repos"):
        super().__init__(
            name="git_tools",
            tools=[
                self.clone_repo,
                self.list_repos,
                self.repo_summary,
                self.git_log,
                self.git_diff,
                self.git_blame,
                self.git_show,
                self.git_branches,
                self.get_github_remote,
            ],
        )
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _repo_path(self, repo: str) -> Path:
        """Resolve a repo name to an absolute path under base_dir.

        Raises:
            ValueError: If the resolved path escapes base_dir or is missing.
        """
        resolved = (self.base_dir / repo).resolve()
        if not resolved.is_relative_to(self.base_dir.resolve()):
            raise ValueError(f"Path escapes base directory: {repo}")
        if not resolved.is_dir():
            raise ValueError(f"Repository not found: {resolved}")
        return resolved

    def _run(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command with standard settings."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )

    @staticmethod
    def _name_from_url(url: str) -> str:
        """Derive a local directory name from a git URL.

        Handles HTTPS (`https://github.com/owner/repo.git`), SSH
        (`git@github.com:owner/repo.git`), and bare `owner/repo` shorthand.
        """
        u = url.strip()
        if u.startswith("git@"):
            _, _, path = u.partition(":")
            last = path.rstrip("/").split("/")[-1]
        elif "://" in u:
            last = urlparse(u).path.rstrip("/").split("/")[-1]
        else:
            last = u.rstrip("/").split("/")[-1]
        return last.removesuffix(".git") or "repo"

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Expand `owner/repo` shorthand to a full GitHub HTTPS URL."""
        u = url.strip()
        if u.startswith(("http://", "https://", "git@")):
            return u
        if re.fullmatch(r"[\w.-]+/[\w.-]+", u):
            return f"https://github.com/{u}.git"
        return u

    # ------------------------------------------------------------------
    # Cloning
    # ------------------------------------------------------------------

    def clone_repo(self, url: str, name: str = "") -> str:
        """Clone a git repository into the scratch directory, or pull if it exists.

        Public repos clone without authentication. Private repos use
        `GITHUB_ACCESS_TOKEN` via the system's git credential helper.
        Accepts full URLs (HTTPS or SSH) or `owner/repo` shorthand for GitHub.

        Args:
            url: Git URL or `owner/repo` GitHub shorthand.
            name: Optional local directory name. Defaults to the
                repository name parsed from the URL.

        Returns:
            A message including the local repo name to pass to other tools.
        """
        try:
            full_url = self._normalize_url(url)
            local_name = name or self._name_from_url(full_url)
            if not re.fullmatch(r"[\w.-]+", local_name):
                return f"Error: invalid repo name: {local_name!r}"

            dest = (self.base_dir / local_name).resolve()
            if not dest.is_relative_to(self.base_dir.resolve()):
                return f"Error: destination escapes base directory: {local_name}"

            if dest.exists() and (dest / ".git").exists():
                result = self._run(
                    ["git", "pull", "--ff-only", "--quiet"],
                    cwd=dest,
                    timeout=120,
                )
                if result.returncode != 0:
                    return (
                        f"Repo '{local_name}' exists but pull failed: "
                        f"{result.stderr.strip() or 'unknown error'}. Use as-is."
                    )
                return f"Updated existing clone: {local_name}"

            if dest.exists():
                return f"Error: {dest} exists and is not a git repository."

            result = self._run(
                ["git", "clone", "--depth=50", full_url, str(dest)],
                timeout=300,
            )
            if result.returncode != 0:
                return f"Error cloning: {result.stderr.strip()}"
            return f"Cloned '{full_url}' to {local_name}"
        except subprocess.TimeoutExpired:
            return "Error: clone timed out after 5 minutes."
        except Exception as e:
            logger.warning(f"clone_repo failed: {e}")
            return f"Error: {e}"

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list_repos(self) -> str:
        """List all cloned repositories in the scratch directory.

        For each repo, shows the current branch and the most recent commit.
        """
        try:
            if not self.base_dir.is_dir():
                return f"Error: base directory does not exist: {self.base_dir}"
            repos: list[str] = []
            for entry in sorted(self.base_dir.iterdir()):
                if entry.is_dir() and (entry / ".git").exists():
                    branch = (
                        self._run(
                            ["git", "branch", "--show-current"],
                            cwd=entry,
                        ).stdout.strip()
                        or "(detached)"
                    )
                    last_commit = (
                        self._run(
                            ["git", "log", "--oneline", "-1"],
                            cwd=entry,
                        ).stdout.strip()
                        or "(no commits)"
                    )
                    repos.append(f"  {entry.name}  ({branch})  {last_commit}")
            if not repos:
                return "(no repos cloned yet — use clone_repo to fetch one)"
            return "Cloned repos:\n" + "\n".join(repos)
        except Exception as e:
            logger.warning(f"list_repos failed: {e}")
            return f"Error: {e}"

    def repo_summary(self, repo: str) -> str:
        """Overview of a cloned repository: branch, top-level files, recent commits, README."""
        try:
            repo_path = self._repo_path(repo)
            sections: list[str] = []

            branch = (
                self._run(
                    ["git", "branch", "--show-current"],
                    cwd=repo_path,
                ).stdout.strip()
                or "(detached)"
            )
            sections.append(f"Branch: {branch}")

            entries = sorted(p.name for p in repo_path.iterdir() if not p.name.startswith("."))
            sections.append("Files:\n  " + "\n  ".join(entries) if entries else "Files: (empty)")

            log_output = self._run(
                ["git", "log", "--oneline", "-5"],
                cwd=repo_path,
            ).stdout.strip()
            sections.append(f"Recent commits:\n{log_output}" if log_output else "Recent commits: (none)")

            readme_names = ["README.md", "README.rst", "README.txt", "README"]
            found_readme = next((r for r in readme_names if (repo_path / r).is_file()), None)
            sections.append(f"README: {found_readme}" if found_readme else "README: (not found)")

            return "\n\n".join(sections)
        except Exception as e:
            logger.warning(f"repo_summary failed: {e}")
            return f"Error: {e}"

    def get_github_remote(self, repo: str) -> str:
        """Return the `owner/repo` identifier from the `origin` remote URL."""
        try:
            repo_path = self._repo_path(repo)
            result = self._run(["git", "remote", "get-url", "origin"], cwd=repo_path)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            url = result.stdout.strip()
            match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
            if not match:
                return f"Error: could not parse GitHub owner/repo from remote URL: {url}"
            return match.group(1)
        except Exception as e:
            logger.warning(f"get_github_remote failed: {e}")
            return f"Error: {e}"

    # ------------------------------------------------------------------
    # Read-only history
    # ------------------------------------------------------------------

    def git_log(
        self,
        repo: str,
        path: str = "",
        n: int = 20,
        since: str = "",
    ) -> str:
        """Show recent git commits for a repository.

        Args:
            repo: Repository name under base_dir.
            path: Optional file or directory path filter.
            n: Maximum commits to return (default 20).
            since: Optional date filter, e.g. '2024-01-01' or '2 weeks ago'.
        """
        try:
            repo_path = self._repo_path(repo)
            cmd = ["git", "log", "--oneline", "-n", str(n)]
            if since:
                cmd.append(f"--since={since}")
            if path:
                cmd += ["--", path]
            result = self._run(cmd, cwd=repo_path)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            return result.stdout.strip() or "(no commits)"
        except Exception as e:
            logger.warning(f"git_log failed: {e}")
            return f"Error: {e}"

    def git_diff(
        self,
        repo: str,
        ref1: str,
        ref2: str = "HEAD",
        path: str = "",
        stat: bool = False,
    ) -> str:
        """Show the diff between two refs.

        Accepts ranges like ``main..feature`` in `ref1` (leave `ref2` empty).
        Full diff output is truncated at 20 000 chars.
        """
        try:
            repo_path = self._repo_path(repo)
            if ".." in ref1:
                cmd = ["git", "diff", ref1]
            else:
                cmd = ["git", "diff", f"{ref1}..{ref2}"]
            if stat:
                cmd.append("--stat")
            if path:
                cmd += ["--", path]
            result = self._run(cmd, cwd=repo_path)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            output = result.stdout.strip()
            if len(output) > 20000:
                return output[:20000] + "\n\n... [truncated — diff exceeds 20 000 chars]"
            return output or "(no diff)"
        except Exception as e:
            logger.warning(f"git_diff failed: {e}")
            return f"Error: {e}"

    def git_blame(
        self,
        repo: str,
        path: str,
        start_line: int = 1,
        end_line: int = 50,
    ) -> str:
        """Line-by-line blame for a range of a file."""
        try:
            repo_path = self._repo_path(repo)
            cmd = ["git", "blame", "-L", f"{start_line},{end_line}", path]
            result = self._run(cmd, cwd=repo_path)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            return result.stdout.strip() or "(no blame output)"
        except Exception as e:
            logger.warning(f"git_blame failed: {e}")
            return f"Error: {e}"

    def git_show(self, repo: str, ref: str) -> str:
        """Show metadata and diffstat for a commit/branch/tag."""
        try:
            repo_path = self._repo_path(repo)
            result = self._run(["git", "show", ref, "--stat"], cwd=repo_path)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            return result.stdout.strip() or "(no output)"
        except Exception as e:
            logger.warning(f"git_show failed: {e}")
            return f"Error: {e}"

    def git_branches(self, repo: str, remote: bool = True) -> str:
        """List branches in a repository."""
        try:
            repo_path = self._repo_path(repo)
            cmd = ["git", "branch"]
            if remote:
                cmd.append("-a")
            result = self._run(cmd, cwd=repo_path)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            return result.stdout.strip() or "(no branches)"
        except Exception as e:
            logger.warning(f"git_branches failed: {e}")
            return f"Error: {e}"
