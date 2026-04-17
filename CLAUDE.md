# CLAUDE.md

## Project Overview

Scout v3 is an **enterprise context agent** — a team of specialists that navigates your company's knowledge graph through a uniform `Source` protocol. The wiki is the map: dumb stores compile into a curated, navigable, user-editable artifact; smart sources are queried live.

## Architecture

```
Scout (Team Leader — coordinate mode)
├── Navigator    — primary user-facing agent. Reads compiled/ + live sources via Source dispatch.
├── Researcher   — Parallel web search + ingest into context/raw/ (conditional on PARALLEL_API_KEY)
├── Compiler     — iterates compile-on sources, writes Obsidian-compat markdown to context/compiled/
├── Linter       — wiki health, source flap, user-edit conflicts, stale articles
├── Syncer       — git push/pull for context/ (conditional on GITHUB_ACCESS_TOKEN)
└── [leader responds directly for greetings/simple questions]
```

## The wiki-first rule

The Compiler turns raw inputs into clean wiki articles. The Navigator reads the wiki, never the raw inputs directly. Two flags on every Source enforce this at the code level:
- `compile=True` → Compiler iterates this source, writes to `context/compiled/`
- `live_read=True` → Navigator can query this source directly

`context/raw/` is `compile=True, live_read=False` and is invisible to the Navigator. Drive is `compile=False, live_read=True`. The Manifest enforces tool-registration boundaries by role.

## Structure

```
scout/
├── __init__.py               # Exports: scout (Team)
├── __main__.py               # CLI: chat | compile | manifest | sources
├── team.py                   # Scout team definition (leader + members)
├── config.py                 # Env vars and feature flags
├── paths.py                  # CONTEXT_*, DOCUMENTS_DIR
├── instructions.py           # Instruction assembly
├── manifest.py               # Runtime capability registry
├── compile_state.py          # Postgres-backed compile state (replaces .state.json)
├── sources/
│   ├── base.py               # Source protocol + Entry/Content/Meta/Hit/HealthStatus
│   ├── local_folder.py       # LocalFolderSource (compile or live-read)
│   ├── drive.py              # GoogleDriveSource (live-read)
│   └── __init__.py           # build_sources() / get_sources() / reload_sources()
├── compile/
│   ├── runner.py             # The compile pipeline. Heart of v3.
│   └── __init__.py
├── agents/
│   ├── settings.py           # Shared DB, knowledge bases
│   ├── navigator.py          # Source-dispatch + SQL + Gmail/Calendar
│   ├── researcher.py         # Parallel + ingest_url/text → context/raw/
│   ├── compiler.py           # Drives compile.runner
│   ├── linter.py             # Wiki health checks
│   └── syncer.py             # Git commit + push
└── tools/
    ├── build.py              # Tool assembly per agent role
    ├── manifest_tools.py     # read_manifest
    ├── sources.py            # list_sources / source_list / source_find / source_read
    ├── compile_tools.py      # list_compile_sources / compile_one / compile_one_source / ...
    ├── knowledge.py          # update_knowledge
    ├── ingest.py             # ingest_url / ingest_text (Researcher)
    ├── git.py                # Git sync tools (Syncer)
    └── redactor.py           # Secret-stripping middleware

context/
├── about-us.md
├── preferences.md
├── voice/
│   ├── email.md
│   ├── slack-message.md
│   ├── document.md
│   └── wiki-article.md       # Voice guide for the Compiler
├── templates/
├── meetings/
├── projects/
├── raw/                      # User-writable intake. Compile-only. Navigator-invisible.
└── compiled/                 # Obsidian-compatible vault. Live-read.
    ├── articles/             # <slug>-<short-hash>.md
    ├── concepts/
    ├── summaries/
    ├── outputs/
    └── index.md              # Auto-regenerated after each compile pass

documents/                    # Read-only enterprise document corpus

app/
├── main.py                   # AgentOS entry (lifespan: migrations + manifest + schedules)
├── router.py                 # /manifest, /compile/run, /sources/{id}/health, /wiki/*, /sync/pull
└── config.yaml

db/
├── session.py                # get_postgres_db / create_knowledge / get_sql_engine
├── url.py                    # DB URL builder
└── migrations.py             # scout_compiled, scout_sources, workspace_id columns

evals/
├── __init__.py               # CATEGORIES (security, routing, ..., wiki_compile, manifest, isolation, drive_live, slack, github_live, s3_compile)
├── __main__.py / run.py
├── cases/                    # static cases
└── live/                     # Docker-hosted harness (SSE + diagnostic + autofix)
    ├── __main__.py           # python -m evals.live run [--case ID]
    ├── cases.py              # EvalCase dataclass + case inventory
    ├── client.py             # SSE POST /teams/scout/runs
    └── runner.py             # assertions + evals/results/<case>.md diagnostic
```

## Commands

```bash
./scripts/venv_setup.sh && source .venv/bin/activate
./scripts/format.sh                   # Format code
./scripts/validate.sh                 # Lint + type check

# CLI
python -m scout                       # Chat
python -m scout sources               # List registered sources + capabilities
python -m scout manifest              # Print the live manifest
python -m scout compile               # Compile every compile-on source (skips unchanged)
python -m scout compile --source local:raw --entry handbook.pdf
python -m scout compile --force       # Re-compile everything

# Context
python context/load_context.py
python context/load_context.py --recreate

# Migrations (also run automatically on app startup)
python -m db.migrations

# Static evals (AccuracyEval / ReliabilityEval / AgentAsJudgeEval)
python -m evals
python -m evals --category wiki_compile

# Live eval harness — hits the Docker-hosted API over SSE
python -m evals.live run                     # all cases; env-missing SKIP
python -m evals.live run --case greeting
./scripts/eval_loop.sh gating_adversarial    # autonomous fix loop

# Smoke tests
python -m scout _smoke_gating                # assert Navigator can't read local:raw
./scripts/validate.sh                        # ruff + mypy + smoke
```

## Sources

| Source id | Kind | Mode | Notes |
|---|---|---|---|
| `local:raw` | LocalFolderSource(./context/raw) | compile-only | Invisible to Navigator — gated by `manifest.can_call`, raises `PermissionError` on violation |
| `local:wiki` | LocalFolderSource(./context/compiled) | live-read | The wiki Navigator reads |
| `drive` | GoogleDriveSource(folder_ids=…) | live-read | Optional — needs Google + `GOOGLE_DRIVE_FOLDER_IDS` |
| `slack` | SlackSource(channel_allowlist=…) | live-read | Optional — needs `SLACK_TOKEN` |
| `github` | GitHubSource(repos=…) | live-read | Optional — needs `GITHUB_REPOS` + `GITHUB_READ_TOKEN`. Clones under `./.scout-cache/repos/` |
| `s3:<bucket>[/<prefix>]` | S3Source | compile-only | Optional — needs `S3_BUCKETS` + `AWS_*`. One instance per entry. |

## Two Knowledge Systems

| System | What It Stores | Prefixes |
|--------|---------------|----------|
| `scout_knowledge` | Metadata routing: where things live | `Wiki:`, `File:`, `Schema:`, `Source:`, `Discovery:`, `Code:` |
| `scout_learnings` | Per-user operational memory | `Retrieval:`, `Pattern:`, `Correction:` |

Both tables carry a `workspace_id` column (Phase 1 default = `'default'`).

## Execution Loop

```
User Question → Classify → Recall (Manifest+Knowledge+Learnings) → Read (Sources) → Act → Learn
```

## Tools by Agent

| Agent | Tools |
|-------|-------|
| Navigator | SQLTools, FileTools (context + documents), MCPTools (Exa), GmailTools, CalendarTools, update_knowledge, read_manifest, source_* |
| Researcher | FileTools, ParallelTools, update_knowledge, ingest_url, ingest_text, read_manifest, source_* |
| Compiler | FileTools (context), update_knowledge, read_manifest, source_* (compile-only), compile_* |
| Linter | FileTools (compiled+context), MCPTools (Exa), update_knowledge, read_manifest, source_* (live-read) |
| Syncer | sync_push, sync_pull, sync_status |

All tool returns are passed through the redactor in `scout.tools.redactor` — secret-shaped strings are stripped before they reach the model.

## Scheduled Tasks

| Task | Schedule | Endpoint |
|------|----------|----------|
| Context Refresh | Daily 8 AM | `/context/reload` |
| Daily Briefing | Weekdays 8 AM | `/teams/scout/runs` |
| **Wiki Compile** | **Every 10 min** | `/compile/run` |
| **Source Health Check** | **Every 15 min** | `/manifest/reload` |
| Inbox Digest | Weekdays 12 PM | `/teams/scout/runs` |
| Learning Summary | Monday 10 AM | `/teams/scout/runs` |
| Weekly Review | Friday 5 PM | `/teams/scout/runs` |
| Wiki Lint | Sunday 8 AM | `/wiki/lint` |
| Sync Pull | Every 30 min | `/sync/pull` |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/teams/scout/runs` | POST | Run the Scout team |
| `/manifest` | GET | Current manifest |
| `/manifest/reload` | POST | Rebuild manifest from sources |
| `/sources/{id}/health` | GET | Per-source health ping |
| `/compile/run` | POST | Run compile pipeline (no body / source_id / source_id+entry_id) |
| `/wiki/compile` | POST | Legacy alias for /compile/run |
| `/wiki/lint` | POST | Trigger Linter agent |
| `/wiki/ingest` | POST | Ingest URL or text into context/raw/ |
| `/context/reload` | POST | Re-index context files |
| `/sync/pull` | POST | Pull remote context/ from GitHub |

## Model

Every agent, the Leader, the compile runner, and the evals judge run on
`Claude(id="claude-opus-4-7")` via `agno.models.anthropic`. The literal
sits at each call site — no `SCOUT_COMPILE_MODEL` / `COMPILE_MODEL_ID`
indirection.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Claude Opus 4.7 — agents + Leader + Compiler + evals judge |
| `OPENAI_API_KEY` | No | Only for `text-embedding-3-small` in the Knowledge path |
| `EXA_API_KEY` | No | Web search for Navigator + Linter (tool loads regardless) |
| `PARALLEL_API_KEY` | No | Enables the Researcher agent + full-content ingest_url |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_PROJECT_ID` | No | Gmail + Calendar + Drive (all three required together) |
| `GOOGLE_DRIVE_FOLDER_IDS` | No | Comma-separated — enables `GoogleDriveSource` |
| `SLACK_TOKEN` | No | Enables Slack Interface + SlackTools + `SlackSource` |
| `SLACK_SIGNING_SECRET` | No | Slack inbound event verification |
| `SLACK_CHANNEL_ALLOWLIST` | No | Comma-separated channel IDs (empty = allow all) |
| `GITHUB_REPOS` | No | Comma-separated `owner/repo` — enables `GitHubSource` |
| `GITHUB_READ_TOKEN` | No | Read-only PAT for `GitHubSource` |
| `S3_BUCKETS` | No | Comma-separated `bucket[:prefix]` — enables `S3Source` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | No | Required when `S3_BUCKETS` is set |
| `GITHUB_ACCESS_TOKEN` | No | Git sync (both required with `SCOUT_REPO_URL`) |
| `SCOUT_REPO_URL` | No | Git sync repo URL |
| `SCOUT_CONTEXT_DIR` | No | Context directory (default: `./context`) |
| `SCOUT_RAW_DIR` | No | Override raw intake dir |
| `SCOUT_COMPILED_DIR` | No | Override compiled wiki dir |
| `SCOUT_VOICE_DIR` | No | Override voice-guide dir |
| `SCOUT_WORKSPACE_ID` | No | Workspace scoping (default: `default`) |
| `SCOUT_API_HOST_PORT` | No | Host port the API publishes on (default: `8000`) |
| `DOCUMENTS_DIR` | No | Documents directory (default: `./documents`) |
| `DB_HOST/PORT/USER/PASS/DATABASE` | No | PostgreSQL config |
| `RUNTIME_ENV` | No | `dev` for hot reload |

## Conventions

### Source

Every external store is a `Source`. Implementations live in `scout/sources/`. Capabilities (`LIST`, `READ`, `METADATA`, `FIND_LEXICAL`, `FIND_NATIVE`, `FIND_SEMANTIC`) are declared per source so callers can dispatch correctly.

### Database

- Use `get_postgres_db()` from `db` module
- Use `create_knowledge()` for Knowledge bases with PgVector hybrid search
- Use `get_sql_engine()` for SQL tools with `scout` schema
- Knowledge bases use `text-embedding-3-small` embedder
- `db/migrations.py` runs at startup; safe to rerun

### Imports

```python
from db import db_url, get_postgres_db, create_knowledge, get_sql_engine, SCOUT_SCHEMA
from scout import scout
from scout.agents.settings import scout_knowledge, scout_learnings
from scout.config import SCOUT_CONTEXT_DIR, SCOUT_RAW_DIR, SCOUT_COMPILED_DIR, WORKSPACE_ID
from scout.sources import get_sources, get_source
from scout.manifest import get_manifest, reload_manifest
from scout.compile import compile_all, compile_source, compile_entry
```
