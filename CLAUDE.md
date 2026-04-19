# CLAUDE.md

## Project Overview

Scout is an **enterprise context agent** — a team of specialists that navigates your company's knowledge graph through a uniform `Source` protocol. The wiki is the map: dumb stores compile into a curated, navigable, user-editable artifact; smart sources are queried live.

## Architecture

```
Scout (Team Leader — coordinate mode)
├── Navigator     — read-only knowledge-graph navigator. Wiki, SQL (SELECT only),
│                   files (read), Drive/Slack/Gmail inbox/Calendar, web search.
├── Compiler      — owns every wiki write path: ingests raw inputs (ingest_url/text
│                   → context/raw/), compiles into context/compiled/, runs lint
│                   checks (broken backlinks, stale articles, needs_split,
│                   user-edit conflicts) after every pass.
├── CodeExplorer  — clones public/PAT-authed git repos on demand into $REPOS_DIR
│                   and answers code questions. Read-only (CodingTools + GitTools
│                   + ReasoningTools).
├── Engineer      — owns SQL writes. Creates scout_* tables on demand, inserts
│                   user-provided notes/facts, records every schema change back to
│                   Knowledge so Navigator can find it.
└── Doctor        — diagnoses Scout's own health (sources, compile state, env,
                    schedules) and self-heals via retry/reload/refresh/cache-clear.
                    Never modifies user content.

Leader handles all outbound communication directly (Slack post, Gmail send,
Calendar write — gated by SCOUT_ALLOW_SENDS).
```

## The wiki-first rule

The Compiler turns raw inputs into clean wiki articles. The Navigator reads the wiki, never the raw inputs directly. Two flags on every Source enforce this at the code level:
- `compile=True` → Compiler iterates this source, writes to `context/compiled/`
- `live_read=True` → Navigator can query this source directly

`context/raw/` is `compile=True, live_read=False` and is invisible to the Navigator. Drive is `compile=False, live_read=True`. The Manifest enforces tool-registration boundaries by role.

## Three write paths, three owners

| Write surface | Owner | Tools |
|---|---|---|
| `context/raw/` + `context/compiled/` | Compiler | `ingest_url`, `ingest_text`, compile pipeline |
| `scout_*` user tables (SQL) | Engineer | DDL + DML, guarded to `scout` schema |
| Outbound (Slack post, Gmail send, Calendar write) | Leader | SlackTools, GmailTools, GoogleCalendarTools (gated by `SCOUT_ALLOW_SENDS`) |

Everything else reads. Navigator and Doctor use the **read-only engine**
(`get_readonly_engine()`) which uses PostgreSQL's `default_transaction_read_only`
setting — any write is rejected at the database level. The Scout engine
(`get_sql_engine()`) is the one Engineer uses; it has a `before_cursor_execute`
hook that rejects any DDL/DML targeting `public` or `ai` as a second-layer
guard.

## Structure

```
scout/
├── __init__.py               # Exports: scout (Team)
├── __main__.py               # CLI: chat | compile | manifest | sources | _smoke_gating
├── team.py                   # Scout team definition (leader + 5 members)
├── settings.py               # Env, feature flags, runtime objects (agent_db, knowledge)
├── paths.py                  # CONTEXT_*
├── instructions.py           # Instruction assembly
├── manifest.py               # Runtime capability registry
├── compile_state.py          # Postgres-backed compile state
├── sources/
│   ├── base.py               # Source protocol + Entry/Content/Meta/Hit/HealthStatus
│   ├── local_folder.py       # LocalFolderSource (compile or live-read)
│   ├── drive.py              # GoogleDriveSource (live-read)
│   ├── slack.py              # SlackSource (live-read)
│   ├── s3.py                 # S3Source (compile-only)
│   └── __init__.py           # get_sources() / reload_sources()
├── compile/
│   ├── runner.py             # The compile pipeline
│   └── __init__.py
├── agents/
│   ├── navigator.py          # Read-only — wiki + SQL SELECT + Gmail/Calendar read + web
│   ├── compiler.py           # Drives compile.runner + ingest + lint
│   ├── code_explorer.py      # On-demand git clone + read-only code exploration
│   ├── engineer.py           # SQL writer — scout_* tables, introspect, update_knowledge
│   └── doctor.py             # Self-diagnosis + retry/reload/refresh/cache-clear
└── tools/
    ├── build.py              # Tool assembly per agent role (+ build_engineer/doctor_tools)
    ├── manifest_tools.py     # read_manifest
    ├── sources.py            # list_sources / source_list / source_find / source_read
    ├── compile_tools.py      # list_compile_sources / compile_one / compile_one_source / ...
    ├── knowledge.py          # update_knowledge
    ├── ingest.py             # ingest_url / ingest_text (Compiler)
    ├── git.py                # GitTools — clone_repo + read-only git helpers (CodeExplorer)
    ├── introspect.py         # introspect_schema (Engineer) — ported from Dash
    ├── diagnostics.py        # health_ping / reload_manifest / retrigger_compile / env_report (Doctor)
    └── redactor.py           # Secret-stripping middleware

context/
├── voice/
│   ├── email.md
│   ├── slack-message.md
│   ├── document.md
│   └── wiki-article.md       # Voice guide for the Compiler (Appendix A verbatim)
├── raw/                      # User-writable intake. Compile-only. Navigator-invisible.
└── compiled/                 # Obsidian-compatible vault. Live-read.
    ├── articles/             # <slug>-<short-hash>.md
    └── index.md              # Auto-regenerated after each compile pass

app/
├── main.py                   # AgentOS entry (lifespan: tables + manifest + schedules)
├── router.py                 # /manifest, /compile/run, /sources/{id}/health, /wiki/ingest, /doctor/*
└── config.yaml

db/
├── session.py                # get_sql_engine (guarded) / get_readonly_engine / get_postgres_db / create_knowledge
├── url.py                    # DB URL builder
└── tables.py                 # Canonical DDL: scout_compiled, scout_sources, scout_contacts/projects/notes/decisions

evals/
├── __init__.py               # CATEGORIES (security, routing, ..., engineer, doctor, code_explorer, s3_compile)
├── __main__.py / run.py
├── cases/                    # Static cases (engineer.py, doctor.py, ...)
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

# Tables (also run automatically on app startup)
python -m db.tables

# Static evals (AccuracyEval / ReliabilityEval / AgentAsJudgeEval)
python -m evals
python -m evals --category engineer

# Live eval harness — hits the Docker-hosted API over SSE
python -m evals.live run                     # all cases; env-missing SKIP
python -m evals.live run --case greeting
./scripts/eval_loop.sh gating_adversarial    # autonomous fix loop

# Smoke tests
python -m scout _smoke_gating                # assert Navigator can't read local:raw
./scripts/validate.sh                        # ruff + mypy + smoke
```

### Environment loading for CLI work

Secrets live in `.env` (and `.envrc` for direnv). If you're running anything that hits OpenAI or Google directly (`python -m evals`, `python -m evals smoke`, `python -m evals improve`, `python -m scout`, `python -m scout compile`, etc.) and the shell reports `OPENAI_API_KEY not set`, the fix is to load the env file — don't ask the user, don't skip, don't fabricate a key. In order:

1. **Prefer direnv:** `direnv allow .` once per repo. After that every shell in this directory has the env.
2. **Fallback (single command):** `set -a; source .env; set +a; python -m evals smoke`
3. **Per-invocation (Bash tool):** prefix the command with `set -a && source .env && set +a && ...`

Docker picks up `.env` automatically via `docker compose`, so code running inside `scout-api` already has everything. Only direct host-shell invocations need the explicit source.

## Sources

| Source id | Kind | Mode | Notes |
|---|---|---|---|
| `local:raw` | LocalFolderSource(./context/raw) | compile-only | Invisible to Navigator — gated by `manifest.can_call`, raises `PermissionError` on violation |
| `local:wiki` | LocalFolderSource(./context/compiled) | live-read | The wiki Navigator reads |
| `drive` | GoogleDriveSource | live-read | Optional — needs Google OAuth. Drive scope managed by sharing folders with Scout's account. |
| `slack` | SlackSource | live-read | Optional — needs `SLACK_BOT_TOKEN`. Channel scope managed by inviting the bot. |
| `s3:<bucket>[/<prefix>]` | S3Source | compile-only | Optional — needs `S3_BUCKETS` + `AWS_*`. One instance per entry. |

Code exploration is **not** modeled as a Source. The `CodeExplorer` agent clones arbitrary git repos on demand into `$REPOS_DIR` (compose: `/repos` named volume; local: `./.scout/repos`) and answers questions by reading the source directly — no manifest entry, no pre-configured repo list.

## User Data Tables

Shipped tables under the `scout` schema (created on first startup via `db/tables.py`). All carry `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ DEFAULT NOW()`.

| Table | Purpose | Domain columns |
|---|---|---|
| `scout_contacts` | People | `name`, `emails TEXT[]`, `phone`, `tags TEXT[]`, `notes` |
| `scout_projects` | Things in motion | `name`, `status`, `tags TEXT[]` |
| `scout_notes` | Free-form notes | `title`, `body`, `tags TEXT[]`, `source_url` |
| `scout_decisions` | Decisions made | `title`, `rationale`, `made_at DATE`, `tags TEXT[]` |

Beyond these four, the Engineer creates new `scout_*` tables on demand (always in the `scout` schema, always with the standard columns, always recording the schema to `scout_knowledge` afterward so Navigator can find it).

## Two Knowledge Systems

| System | What It Stores | Prefixes |
|--------|---------------|----------|
| `scout_knowledge` | Metadata routing: where things live | `Wiki:`, `File:`, `Schema:`, `Source:`, `Discovery:`, `Code:` |
| `scout_learnings` | Per-user operational memory | `Retrieval:`, `Pattern:`, `Correction:` |


## Execution Loop

```
User Question → Classify → Recall (Manifest+Knowledge+Learnings) → Read (Sources) → Act → Learn
```

## Tools by Agent

| Agent | Tools |
|-------|-------|
| Navigator | SQLTools (**read-only engine**), FileTools (context, read-only), web search (ParallelTools or Exa MCP), GmailTools (read-only), CalendarTools (read-only), update_knowledge, read_manifest, source_* |
| Compiler | FileTools (context), update_knowledge, read_manifest, source_* (compile-only), compile_*, `ingest_url`, `ingest_text` — runs lint after each compile pass |
| CodeExplorer | CodingTools (read_file, grep, find, ls — read-only), GitTools (clone_repo, git_log/diff/blame/show/branches, repo_summary, list_repos, get_github_remote), ReasoningTools |
| Engineer | SQLTools (scout engine, **schema-guarded** to scout), introspect_schema, update_knowledge, ReasoningTools |
| Doctor | SQLTools (**read-only**), FileTools (repo root, read-only — for docs/* reads), read_manifest, reload_manifest, health_ping, retrigger_compile, clear_repo_cache, env_report |
| Leader | FileTools (voice/, read-only), SQLTools (**read-only**, for contact lookup), SlackTools (send-capable when SLACK_BOT_TOKEN set), GmailTools + GoogleCalendarTools (gated by `SCOUT_ALLOW_SENDS`) |

All tool returns are passed through the redactor in `scout.tools.redactor` — secret-shaped strings are stripped before they reach the model.

## Scheduled Tasks

| Task | Schedule | Endpoint |
|------|----------|----------|
| Daily Briefing | Weekdays 8 AM | `/teams/scout/runs` |
| **Wiki Compile** | **Hourly on :00** | `/compile/run` (lint runs inside each pass). A one-shot compile also fires at container boot so the wiki is populated within ~30s of startup. |
| **Source Health Check** | **Every 15 min** | `/manifest/reload` |
| **Doctor Daily** | **Daily 9 AM (local)** | `/doctor/run` — self-diagnostic report |
| Inbox Digest | Weekdays 12 PM | `/teams/scout/runs` |
| Learning Summary | Monday 10 AM | `/teams/scout/runs` |
| Weekly Review | Friday 5 PM | `/teams/scout/runs` |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/teams/scout/runs` | POST | Run the Scout team |
| `/manifest` | GET | Current manifest |
| `/manifest/reload` | POST | Rebuild manifest from sources |
| `/sources/{id}/health` | GET | Per-source health ping |
| `/compile/run` | POST | Run compile pipeline (no body / source_id / source_id+entry_id) |
| `/wiki/compile` | POST | Legacy alias for /compile/run |
| `/wiki/ingest` | POST | Ingest URL or text into context/raw/ |
| `/doctor/run` | POST | Run a Doctor diagnostic pass — returns report JSON |
| `/doctor/health` | GET | Liveness probe (DB reachable?) |

## Model

Every agent, the Leader, the compile runner, and the evals judge run on `OpenAIResponses(id="gpt-5.4")` via `agno.models.openai`. The literal sits at each call site — no `SCOUT_COMPILE_MODEL` / `COMPILE_MODEL_ID` indirection. OpenAI is also what `text-embedding-3-small` uses for the Knowledge/Learnings PgVector path, so one key covers everything.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **Yes** | GPT-5.4 for every agent + embeddings for Knowledge |
| `PARALLEL_API_KEY` | No | Premium web search + extraction. When unset, Scout falls back to Exa's public MCP endpoint (keyless) — Navigator always has a web-search backend. |
| `EXA_API_KEY` | No | Optional. Raises rate limits on the Exa MCP fallback; not required to use it. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_PROJECT_ID` | No | Scout's own Google app — Gmail + Calendar + Drive (all three required together). Drive scope is managed on the Google side by sharing folders with Scout's account. |
| `SLACK_BOT_TOKEN` | No | Scout's Slack bot token (xoxb-…) — enables Slack Interface + SlackTools + `SlackSource` |
| `SLACK_SIGNING_SECRET` | No | Slack inbound event verification |
| `SCOUT_ALLOW_SENDS` | No | When `true`, Leader can actually send Gmail / modify Calendar. Default `false` = drafts-only. Slack is always opt-in via `SLACK_BOT_TOKEN`. |
| `GITHUB_ACCESS_TOKEN` | No | Optional PAT for CodeExplorer. Public repos clone tokenless; set this for private repos or to raise the API rate ceiling |
| `REPOS_DIR` | No | Where CodeExplorer clones repos. Compose sets `/repos` (the `repos` named volume); local falls back to `.scout/repos` |
| `S3_BUCKETS` | No | Comma-separated `bucket[:prefix]` — enables `S3Source` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | No | Required when `S3_BUCKETS` is set |
| `SCOUT_CONTEXT_DIR` | No | Context directory (default: `./context`) |
| `SCOUT_RAW_DIR` | No | Override raw intake dir |
| `SCOUT_COMPILED_DIR` | No | Override compiled wiki dir |
| `SCOUT_VOICE_DIR` | No | Override voice-guide dir |
| `DB_HOST/PORT/USER/PASS/DATABASE` | No | PostgreSQL config |
| `RUNTIME_ENV` | No | `dev` for hot reload |

## Conventions

### Source

Every external store is a `Source`. Implementations live in `scout/sources/`. Capabilities (`LIST`, `READ`, `METADATA`, `FIND_LEXICAL`, `FIND_NATIVE`, `FIND_SEMANTIC`) are declared per source so callers can dispatch correctly.

### Database

- Use `get_postgres_db()` from `db` module
- Use `create_knowledge()` for Knowledge bases with PgVector hybrid search
- Use `get_sql_engine()` for SQL tools that need to write to the `scout` schema (Engineer, compile runner, manifest). This engine has a guard that rejects writes to `public` / `ai`.
- Use `get_readonly_engine()` for SQL tools that should never write (Navigator, Doctor, Leader). This engine uses PostgreSQL's `default_transaction_read_only` — rejection happens at the DB level.
- Knowledge bases use `text-embedding-3-small` embedder
- `db/tables.py` runs at startup; safe to rerun

### Imports

```python
from db import db_url, get_postgres_db, create_knowledge, get_sql_engine, get_readonly_engine, SCOUT_SCHEMA
from scout import scout
from scout.settings import (
    SCOUT_CONTEXT_DIR, SCOUT_RAW_DIR, SCOUT_COMPILED_DIR,
    scout_knowledge, scout_learnings,
)
from scout.sources import get_sources, get_source
from scout.manifest import get_manifest, reload_manifest
from scout.compile import compile_all, compile_source, compile_entry
```
