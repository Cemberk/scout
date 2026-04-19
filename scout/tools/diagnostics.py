"""Diagnostic tools for the Doctor agent.

The Doctor diagnoses Scout's own health and self-heals via retry / reload
/ refresh / cache-clear. It never modifies user content — the only files
it can delete are under ``REPOS_DIR`` (the CodeExplorer clone cache),
and its SQL access is read-only.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agno.tools import tool

# Expected environment variables, grouped by integration. Values are
# descriptions shown back to the user, not live env reads.
_EXPECTED_ENV: dict[str, dict[str, str]] = {
    "core": {
        "OPENAI_API_KEY": "GPT-5.4 for every agent + embeddings",
    },
    "web": {
        "PARALLEL_API_KEY": "Premium web search (optional — keyless Exa fallback used otherwise)",
        "EXA_API_KEY": "Raises Exa rate limits (optional)",
    },
    "google": {
        "GOOGLE_CLIENT_ID": "Google OAuth (Drive + Gmail + Calendar)",
        "GOOGLE_CLIENT_SECRET": "Google OAuth",
        "GOOGLE_PROJECT_ID": "Google OAuth",
    },
    "slack": {
        "SLACK_BOT_TOKEN": "Scout's Slack bot token — enables SlackSource + Slack interface",
        "SLACK_SIGNING_SECRET": "Verifies inbound Slack events",
    },
    "code_explorer": {
        "GITHUB_ACCESS_TOKEN": "Optional PAT — public repos clone tokenless",
        "REPOS_DIR": "Clone cache (default .scout/repos; compose uses /repos)",
    },
    "s3": {
        "S3_BUCKETS": "Comma-separated bucket[:prefix]",
        "AWS_ACCESS_KEY_ID": "Required when S3_BUCKETS is set",
        "AWS_SECRET_ACCESS_KEY": "Required when S3_BUCKETS is set",
        "AWS_REGION": "Required when S3_BUCKETS is set",
    },
    "db": {
        "DB_HOST": "Postgres host (default localhost)",
        "DB_PORT": "Postgres port (default 5432)",
        "DB_USER": "Postgres user (default ai)",
        "DB_DATABASE": "Postgres database (default ai)",
    },
}


@tool
def reload_manifest_tool() -> str:
    """Rebuild the Manifest by health-checking every source.

    Returns a summary of each source's status (``connected`` /
    ``degraded`` / ``disconnected`` / ``unconfigured``) + the refreshed
    count.
    """
    from scout.manifest import reload_manifest

    m = reload_manifest()
    lines = [f"Manifest rebuilt. {len(m.sources)} sources:"]
    for s in m.sources.values():
        lines.append(f"- {s.id} ({s.kind}): {s.status} — {s.detail or 'ok'}")
    return "\n".join(lines)


@tool
def health_ping(source_id: str) -> str:
    """Health-check one source and refresh its manifest row.

    Args:
        source_id: Source ID (e.g. "local:wiki", "drive", "slack").

    Returns:
        JSON string with state + detail.
    """
    from scout.manifest import reload_manifest
    from scout.sources import get_source

    s = get_source(source_id)
    if s is None:
        return json.dumps({"error": f"unknown source: {source_id}"})
    h = s.health()
    # Refresh the manifest so the new status is visible to everyone.
    reload_manifest()
    return json.dumps({"source_id": source_id, "state": h.state.value, "detail": h.detail})


@tool
def retrigger_compile(source_id: str | None = None, entry_id: str | None = None, force: bool = False) -> str:
    """Re-run the compile pipeline.

    Args:
        source_id: Restrict to one source. Omit to compile every compile-on source.
        entry_id: Restrict to one entry within ``source_id``. Ignored if ``source_id`` is None.
        force: Re-compile even if the source hash hasn't changed.

    Returns:
        JSON string summarising per-source status counts.
    """
    from collections import Counter
    from dataclasses import asdict

    from scout.compile import compile_all, compile_entry, compile_source
    from scout.settings import scout_knowledge
    from scout.sources import get_source

    if entry_id and not source_id:
        return json.dumps({"error": "entry_id requires source_id"})

    if entry_id and source_id:
        src = get_source(source_id)
        if src is None:
            return json.dumps({"error": f"unknown source: {source_id}"})
        result = compile_entry(src, entry_id, knowledge=scout_knowledge, force=force)
        return json.dumps(asdict(result))

    if source_id:
        results = compile_source(source_id, knowledge=scout_knowledge, force=force)
        counts = Counter(r.status for r in results)
        return json.dumps({"source_id": source_id, "counts": dict(counts)})

    all_results = compile_all(knowledge=scout_knowledge, force=force)
    summary = {sid: dict(Counter(r.status for r in rs)) for sid, rs in all_results.items()}
    return json.dumps(summary)


@tool
def clear_repo_cache(repo_name: str) -> str:
    """Delete one cloned repo under ``REPOS_DIR``.

    Use when a CodeExplorer clone is corrupted (half-cloned, wrong branch,
    stale after a force-push). Next CodeExplorer call for that repo
    re-clones cleanly.

    Args:
        repo_name: Repo directory name under REPOS_DIR — usually "owner_repo"
            or "owner__repo" depending on the clone_repo convention.

    Returns:
        Status string.
    """
    from scout.settings import REPOS_DIR

    target = Path(REPOS_DIR) / repo_name
    # Refuse to delete anything outside REPOS_DIR — tight containment.
    try:
        target_resolved = target.resolve()
        repos_resolved = Path(REPOS_DIR).resolve()
        target_resolved.relative_to(repos_resolved)
    except (ValueError, OSError) as e:
        return f"error: {repo_name} is not inside REPOS_DIR ({e})"

    if not target.exists():
        return f"nothing to clear: {target} does not exist"
    if not target.is_dir():
        return f"error: {target} is not a directory"
    shutil.rmtree(target, ignore_errors=True)
    return f"cleared: {target}"


@tool
def env_report() -> str:
    """Report which environment variables are set, grouped by integration.

    Never leaks values — reports presence only ("set" / "missing") plus
    the description of what the variable unlocks. Use this to answer
    "why isn't Drive showing up?" / "is Slack configured?" without ever
    revealing a secret.
    """
    from os import getenv

    lines: list[str] = []
    for group, vars_ in _EXPECTED_ENV.items():
        lines.append(f"## {group}")
        for name, desc in vars_.items():
            present = "set" if getenv(name) else "missing"
            lines.append(f"- `{name}` ({present}) — {desc}")
        lines.append("")
    return "\n".join(lines)
