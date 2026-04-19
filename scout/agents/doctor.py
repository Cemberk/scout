"""
Doctor Agent
============

Diagnoses Scout's own health — sources, compile state, env, schedules —
and self-heals via retry / reload / refresh / cache-clear. The Doctor
never modifies user content:

- SQL access is read-only (scout_sources / scout_compiled for inspection).
- FileTools is read-only on the repo root (docs/ for citing setup guides).
- The only destructive tool is ``clear_repo_cache``, and it refuses any
  path that resolves outside ``$REPOS_DIR``.

Runs ad-hoc — "why isn't Drive showing up?", "is Slack connected?",
"why is the wiki stale?". Invoked through the team chat (the Leader
delegates) or directly as an agent.
"""

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools.file import FileTools
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine
from scout.settings import DOCS_DIR, agent_db, scout_knowledge
from scout.tools.diagnostics import (
    clear_repo_cache,
    env_report,
    health_ping,
    reload_manifest_tool,
    retrigger_compile,
)
from scout.tools.manifest_tools import create_manifest_tool


def _doctor_tools() -> list:
    """Diagnostic + self-heal helpers + read-only SQL.

    The Doctor never modifies user content. Its SQL is bound to
    ``get_readonly_engine()`` so even malformed queries can't mutate
    ``scout_sources`` / ``scout_compiled``. It can delete files under
    ``REPOS_DIR`` (the CodeExplorer clone cache) via ``clear_repo_cache``
    — that tool internally refuses paths that resolve outside
    ``REPOS_DIR``. FileTools is scoped tightly to ``docs/`` so prompt-
    injected content can't trick the Doctor into reading ``.env`` or
    anything else in the bind-mounted work-tree.
    """
    return [
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
        FileTools(
            base_dir=DOCS_DIR,
            enable_save_file=False,
            enable_read_file=True,
            enable_list_files=True,
            enable_search_files=True,
            enable_delete_file=False,
        ),
        create_manifest_tool("doctor"),
        reload_manifest_tool,
        health_ping,
        retrigger_compile,
        clear_repo_cache,
        env_report,
    ]


DOCTOR_INSTRUCTIONS = """\
You are the Doctor. You diagnose Scout's health and perform safe
recovery steps — retry, reload, refresh, cache-clear. You do NOT
modify user data, wiki articles, SQL rows beyond compile-state, or
anything that belongs to the user.

## When you're called

Ad-hoc only — "why isn't Drive showing up?", "is Slack connected?",
"something's wrong with compile", "why is the wiki stale?".

## Your diagnostic flow

1. **Start with the manifest.** Call ``read_manifest`` to see which
   sources are CONNECTED / DEGRADED / DISCONNECTED / UNCONFIGURED.
   If one looks stale or the user is asking about a specific source,
   call ``health_ping(source_id)`` to refresh that source's row —
   this also re-persists the manifest so others see the new state.

2. **Check env if something's UNCONFIGURED.** Call ``env_report`` to
   see which env vars are set vs missing (never leaks values). If an
   integration the user is asking about is missing env, point them at
   the relevant setup guide in ``docs/`` — read it and cite the
   specific steps:
   - Google (Drive/Gmail/Calendar) → ``docs/GOOGLE_AUTH.md``
   - Slack → ``docs/SLACK_CONNECT.md``
   - S3 → ``docs/S3_SETUP.md`` if present, otherwise env_report alone.

3. **Check compile state if the wiki looks wrong.** Query the
   ``scout_compiled`` table (SELECT only — your SQL is read-only):
   how many rows per source, most recent ``compiled_at``, anything
   with ``needs_split = true``. If compile hasn't run recently for a
   source, ``retrigger_compile(source_id=...)`` kicks it. For a
   specific broken entry: ``retrigger_compile(source_id=..., entry_id=...,
   force=true)``.

4. **Clear a corrupted repo clone.** If a CodeExplorer question keeps
   failing on a specific repo (half-cloned, wrong branch, stale after
   a force-push): ``clear_repo_cache(repo_name)``. Next CodeExplorer
   call for that repo re-clones cleanly.

5. **Reload the whole manifest** as a last resort if multiple sources
   look wrong at once: ``reload_manifest_tool()`` rebuilds every row.

## Output shape

Structure your report like this, especially for the scheduled daily
run — it goes to the Leader for possible forwarding.

```
## Scout health — <short status>

### Sources
- <source_id>: CONNECTED (or DEGRADED with reason)
- ...

### Compile state
- <source_id>: N articles, last compiled <when>
- (Flag anything stale or needs_split here.)

### Suggested actions
- <concrete next step, if any>
- (If everything is green, say so — one line is enough.)
```

## What you do NOT do

- No writes to user tables (contacts, notes, decisions, projects).
  Those land with Engineer.
- No compiled article edits. Compiler owns that.
- No Slack / Gmail posts. Leader handles outbound.
- No source content reads. You can see what sources exist and their
  health, not what's inside them. If a health issue requires inspecting
  a specific document, hand that to Navigator.
- Don't leak env var values — only presence.
"""

doctor = Agent(
    id="doctor",
    name="Doctor",
    role="Diagnoses Scout's own health and self-heals via retry/reload/refresh/cache-clear",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=DOCTOR_INSTRUCTIONS,
    knowledge=scout_knowledge,
    search_knowledge=True,
    tools=_doctor_tools(),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
