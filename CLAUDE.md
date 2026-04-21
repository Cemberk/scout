# CLAUDE.md

## Project Overview

Scout is an **enterprise context agent** — a four-role team coordinated by a Leader, built on top of the `ContextProvider` base class:

- **`ContextProvider`** (query + health + get_tools) — live-read sources. `LocalContextProvider`, `GithubContextProvider`, `S3ContextProvider`, `SlackContextProvider`, `GmailContextProvider`, `DriveContextProvider`. Any subset registered at startup from `SCOUT_CONTEXTS`.
- **`WikiContextProvider`** — the one compile-capable knowledge store. Subclasses `ContextProvider` and adds `ingest_url` / `ingest_text` / `compile`. Composes a `WikiBackend` — `LocalWikiBackend` (dev), `GithubWikiBackend` (prod, git-coordinated), or `S3WikiBackend` (prod, S3 conditional PUT). Configured via `SCOUT_WIKI`.

Compile lives in exactly one place (`WikiContextProvider`). Everything else is read-only. Multi-container works because the wiki provider coordinates through its backend's substrate — never through Scout's process.

Reference spec for the Agno move: [tmp/context_provider.md](tmp/context_provider.md).

## Architecture

```
Scout (Team Leader — coordinate mode)
├── Explorer  — answers questions by asking the wiki + registered contexts.
│               SQL read-only (scout_* tables). Shares scout_learnings.
├── Engineer  — owns every non-outbound write:
│                 · scout_* user-data tables (DDL + DML in the scout schema)
│                 · the wiki (ingest_url / ingest_text / trigger_compile)
│               Shares scout_learnings.
└── Doctor    — diagnoses health: wiki, contexts, DB, env. Read-only
                everywhere. Shares scout_learnings.

Leader handles outbound directly (Slack post, Gmail send, Calendar write —
gated by SCOUT_ALLOW_SENDS). Read-only SQL for contact lookups.
```

## The wiki-first rule

The wiki is the one write surface for knowledge; live contexts are read-only by construction. Two-way boundary:

- **Wiki inputs** land under `raw/` on the wiki provider's backend. `ingest_url` / `ingest_text` write there; `compile` reads `raw/`, LLM-transforms, writes `compiled/`, updates `.scout/state.json`.
- **Wiki reads** go through `WikiContextProvider.query()`. The internal query agent reads `compiled/` via the backend — never the filesystem directly.

Backends are swappable per deploy (`LocalWikiBackend` / `GithubWikiBackend` / `S3WikiBackend`); the pipeline is the same across all three.

## Three write paths, two owners

| Write surface | Owner | Call |
|---|---|---|
| `scout_*` user-data tables | Engineer | SQL DDL + DML, scoped to the `scout` schema (write guard + `get_sql_engine()`) |
| Wiki substrate (raw + compiled + state) | Engineer (via `wiki.get_tools(include_writes=True)`) | `ingest_url`, `ingest_text`, `trigger_compile` |
| Outbound (Slack post, Gmail send, Calendar write) | Leader | SlackTools / GmailTools / GoogleCalendarTools (gated by `SCOUT_ALLOW_SENDS`) |

Everything else reads. Explorer and Doctor use the **read-only engine** (`get_readonly_engine()` — PostgreSQL's `default_transaction_read_only`). The scout engine (`get_sql_engine()`) is the one Engineer uses; it has a `before_cursor_execute` hook that rejects any DDL/DML targeting `public` or `ai` as a second-layer guard.

## Structure

```
scout/
├── __init__.py
├── __main__.py                     # CLI: chat | compile | contexts
├── team.py                         # Leader + three specialists, coordinate mode
├── settings.py                     # Env, paths, DB-dependent runtime objects
├── instructions.py                 # explorer_instructions()
├── agents/
│   ├── explorer.py                 # per-provider query_* + list_contexts + read-only SQL
│   ├── engineer.py                 # SQL writes + wiki.get_tools(include_writes=True)
│   └── doctor.py                   # health / health_all / db_health / env_report
├── context/
│   ├── base.py                     # ContextProvider (ABC) + WikiBackend (Protocol)
│   ├── config.py                   # build_wiki / build_contexts / parse_spec
│   ├── _shared.py                  # answer_from_run, google_env_missing, google_auth_material_missing
│   ├── _git.py                     # shared clone_url / ensure_clone / run
│   ├── _s3.py                      # shared boto3 client + prefix normalizer
│   ├── wiki/
│   │   ├── provider.py             # WikiContextProvider (compile + ingest)
│   │   └── backends/
│   │       ├── local.py            # LocalWikiBackend (dev)
│   │       ├── github.py           # GithubWikiBackend (commit + push, pull-rebase retry)
│   │       └── s3.py               # S3WikiBackend (conditional PUT on state)
│   ├── web/
│   │   ├── provider.py             # WebContextProvider (default-on; Exa MCP or Parallel)
│   │   └── backends/
│   │       ├── exa_mcp.py          # ExaMCPBackend (keyless Exa MCP server)
│   │       └── parallel.py         # ParallelBackend (parallel-web SDK)
│   ├── local/provider.py           # LocalContextProvider
│   ├── github/provider.py          # GithubContextProvider
│   ├── s3/provider.py              # S3ContextProvider
│   ├── slack/provider.py           # SlackContextProvider
│   ├── gmail/provider.py           # GmailContextProvider
│   └── drive/provider.py           # DriveContextProvider
└── tools/
    ├── ask_context.py              # set_runtime / get_wiki / get_contexts / list_contexts
    ├── diagnostics.py              # health / health_all / db_health / env_report (Doctor)
    ├── introspect.py               # introspect_schema (Engineer)
    ├── learnings.py                # create_update_learnings (all three specialists)
    └── redactor.py                 # Secret-stripping middleware

context/
├── voice/                          # Voice guides (read-only)
│   ├── email.md                    #   Leader — email drafts
│   ├── slack-message.md            #   Leader — Slack posts
│   ├── document.md                 #   Leader — long-form drafts
│   └── wiki-article.md             #   WikiContextProvider.compile — article style
└── raw/                            # Sample content LocalWikiBackend reads in dev

app/
├── main.py                         # AgentOS entry (lifespan wires wiki + contexts)
├── router.py                       # /wiki/* + /contexts/* (§7.5 surface)
└── config.yaml

db/
├── session.py                      # get_sql_engine (guarded) / get_readonly_engine
├── url.py                          # DB URL builder
└── tables.py                       # Canonical DDL: scout_contacts / projects /
                                    # notes / decisions.

evals/
├── cases.py                        # Behavioral Case dataclass + CASES tuple
├── runner.py                       # In-process + SSE transports + fixtures
├── wiring.py                       # Code-level invariants (no LLM)
├── judges.py                       # LLM-scored quality tier (voice + grounded-answer)
└── __main__.py                     # CLI dispatch
```

## Commands

```bash
./scripts/venv_setup.sh && source .venv/bin/activate
./scripts/format.sh                   # Format code
./scripts/validate.sh                 # ruff + mypy + wiring invariants

# CLI
python -m scout                       # Chat
python -m scout contexts              # Wiki + registered contexts + health
python -m scout compile               # One wiki compile pass
python -m scout compile --force       # Recompile unchanged entries too

# Tables (also run automatically on app startup)
python -m db.tables

# Evals
python -m evals wiring                # Code-level invariants (no LLM)
python -m evals                       # Behavioral cases, in-process
python -m evals --case <id>           # Single case
python -m evals --live                # Same cases over SSE
python -m evals judges                # LLM-scored quality tier
./scripts/eval_loop.sh <case_id>      # Autonomous fix loop (claude -p)
```

### Environment loading for CLI work

Secrets live in `.env` (and `.envrc` for direnv). Anything that hits OpenAI / Google directly from the host (`python -m evals`, `python -m scout compile`, etc.) needs `.env` loaded. In order:

1. **Prefer direnv:** `direnv allow .` once per repo.
2. **Fallback:** `set -a; source .env; set +a; python -m evals`
3. **Per-invocation (Bash tool):** `set -a && source .env && set +a && ...`

Docker picks up `.env` automatically via `docker compose`, so code inside `scout-api` has everything. Only direct host-shell invocations need the explicit source.

## Contexts

Registered from `SCOUT_CONTEXTS` — comma-separated spec strings. Spec syntax is `<kind>[:<param>]`.

| Kind | Spec example | Constructor | Notes |
|---|---|---|---|
| `slack` | `slack` | `SlackContextProvider()` | Needs `SLACK_BOT_TOKEN`. Read-only; send/upload/download excluded. |
| `gmail` | `gmail` | `GmailContextProvider()` | Needs `GOOGLE_*` + `token.json`. Read-only; every write/modify tool excluded. |
| `drive` | `drive` | `DriveContextProvider()` | Needs `GOOGLE_*` + `token.json`. Read-only; upload excluded. |
| `local` | `local:./context/raw` | `LocalContextProvider(path)` | Agent gets `read_file` / `grep` / `list_dir` scoped to path. |
| `github` | `github:agno-agi/agno` | `GithubContextProvider(repo)` | Clones to `$REPOS_DIR/<owner>__<repo>` on first use. Agent adds `git_log` / `git_blame` / `git_diff` / `git_show`. |
| `s3` | `s3:acme-docs/reports` | `S3ContextProvider(bucket, prefix)` | Needs `AWS_*`. Agent gets `list_keys` / `head_object` / `get_object`. |

**Default: the `WebContextProvider` is prepended automatically** — zero config needed. `ParallelBackend` if `PARALLEL_API_KEY` is set, else keyless `ExaMCPBackend` (Exa's public MCP server). Disable with `SCOUT_DISABLE_WEB=true`. Exposes `query_web` as a tool.

Every Context is **agentic** — `.query()` wraps an internal Agno sub-agent with tools specific to the substrate (spec §5.3). Fresh-per-query for now; cache later if traffic warrants.

## Wiki backends

Chosen via `SCOUT_WIKI` using the same spec syntax.

| Spec | Backend | Concurrency |
|---|---|---|
| `local:./context` (default) | `LocalWikiBackend` | None — single-container only |
| `github:agno-agi/scout-context` | `GithubWikiBackend` | git push rejection → pull-rebase, retry up to 3× |
| `s3:scout-wiki/prod` | `S3WikiBackend` | Conditional PUT on `.scout/state.json` via `If-Match` etag |

Layout is the same across backends:

- `raw/<slug>-<short-sha>.md` — ingested content
- `compiled/<slug>-<hash>.md` — compiled articles
- `.scout/state.json` — `{"entries": [{"entry_id", "source_hash", "compiled_path", "compiled_at"}, ...]}`

## User Data Tables

Shipped tables under the `scout` schema (created on first startup via `db/tables.py`). All carry `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ DEFAULT NOW()`.

| Table | Purpose | Domain columns |
|---|---|---|
| `scout_contacts` | People | `name`, `emails TEXT[]`, `phone`, `tags TEXT[]`, `notes` |
| `scout_projects` | Things in motion | `name`, `status`, `tags TEXT[]` |
| `scout_notes` | Free-form notes | `title`, `body`, `tags TEXT[]`, `source_url` |
| `scout_decisions` | Decisions made | `title`, `rationale`, `made_at DATE`, `tags TEXT[]` |

Beyond these four, Engineer creates new `scout_*` tables on demand — always in the `scout` schema, always with the standard columns, always recording the new shape into `scout_learnings` afterward so Explorer can find it.

## Learnings

One operational-memory store: `scout_learnings`. Explorer, Engineer, Doctor all attach it as their `LearningMachine`'s knowledge base in agentic mode. Routing hints, corrections, per-user preferences — Scout's memory *about itself*. `update_learnings(note, title=?)` writes; the LearningMachine searches before saving so duplicates don't pile up.

## Execution Loop

```
User Question → Leader routes → Specialist answers → Leader synthesizes
```

Explorer's fan-out across wiki + contexts is informed by Learnings ("handbook stuff lives in wiki", "infra is in slack").

## Tools by Agent

| Agent | Tools |
|-------|-------|
| Explorer | `SQLTools` (**read-only engine**, `scout` schema), `query_<id>` (one per registered provider via `provider.get_tools()`), `list_contexts`, `update_learnings` |
| Engineer | `SQLTools` (scout engine, **schema-guarded** to `scout`), `introspect_schema`, `wiki.get_tools(include_writes=True)` → `query_wiki` + `ingest_url` + `ingest_text` + `trigger_compile`, `update_learnings`, `ReasoningTools` |
| Doctor | `SQLTools` (**read-only**), `health`, `health_all`, `db_health`, `env_report`, `update_learnings` |
| Leader | `FileTools` (`voice/`, read-only), `SQLTools` (**read-only**, for contact lookup), `SlackTools` (send-capable when `SLACK_BOT_TOKEN` set), `GmailTools` + `GoogleCalendarTools` (gated by `SCOUT_ALLOW_SENDS`) |

**Per-provider tools are built by the registry.** `scout.tools.ask_context.set_runtime(wiki, contexts)` installs the singletons and rewires Explorer + Engineer's `.tools` list in one call. The app lifespan calls it once at startup; eval fixtures call it per case when they swap providers.

Every `query_<id>` tool's output is scrubbed through `scout.tools.redactor` before reaching the model — OpenAI/Anthropic keys, GitHub PATs, Slack tokens, AWS keys, JWTs, and shaped env-var pairs (`*_PASSWORD=…`, `*_SECRET=…`, `*_TOKEN=…`) are redacted. Defensive: the substrate should never surface secrets, but if it does, the redactor catches it before the model sees it.

## Scheduled Tasks

None registered in this build. To run compile on a cadence, either:

- `docker exec -it scout-api python -m scout compile` on a host-side cron, or
- `POST /wiki/compile` from an external scheduler, or
- ask Engineer "compile now" in chat.

§8 Phase 3 calls for a scheduler pod posting to `/wiki/compile` on the API LB as the recommended shape for multi-container deploys.

## API Endpoints

On top of AgentOS's defaults (`/teams/scout/runs`, `/health`, …), the custom endpoints are:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/wiki/health` | GET | Wiki health |
| `/wiki/compile` | POST | Run one compile pass (body: `{"force": bool}`) |
| `/wiki/ingest` | POST | Ingest URL / text (body: `{"kind": "url"\|"text", "title": ..., ...}`) |
| `/wiki/query` | POST | Debug: ask the wiki directly |
| `/contexts` | GET | List wiki + every registered context + health |
| `/contexts/{id}/health` | GET | One target's health |
| `/contexts/{id}/query` | POST | Debug: ask one target directly |

## Model

Every agent, the Leader, the compile runner, and the evals judge run on `OpenAIResponses(id="gpt-5.4")` via `agno.models.openai`. The literal sits at each call site — no env indirection. OpenAI is also what `text-embedding-3-small` uses for the Learnings PgVector path, so one key covers everything.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **Yes** | GPT-5.4 for every agent + embeddings for Learnings |
| `SCOUT_WIKI` | No | Wiki backend spec. Default `local:./context`. Prod: `github:<owner>/<repo>` or `s3:<bucket>[/<prefix>]`. |
| `SCOUT_CONTEXTS` | No | Comma-separated live-read context specs. Empty by default. |
| `PARALLEL_API_KEY` | No | Premium web research for `WebContextProvider`. When set, Scout swaps to `ParallelBackend`; otherwise the default is keyless `ExaMCPBackend`. |
| `EXA_API_KEY` | No | Optional. Raises rate limits on `ExaMCPBackend`; not required. |
| `SCOUT_DISABLE_WEB` | No | Set to `true` to drop the default `WebContextProvider`. Useful in private-network deployments. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_PROJECT_ID` | No | Scout's Google OAuth app — Gmail + Calendar + Drive. Run `python scripts/google_auth.py` once to generate `token.json`. |
| `SLACK_BOT_TOKEN` | No | Scout's Slack bot token (xoxb-…) — enables the Slack interface, Leader's SlackTools, and `SlackContextProvider`. |
| `SLACK_SIGNING_SECRET` | No | Verifies inbound Slack events (Slack interface). |
| `SCOUT_ALLOW_SENDS` | No | When `true`, Leader can actually send Gmail / modify Calendar. Default `false` = drafts-only. |
| `GITHUB_ACCESS_TOKEN` | No | Optional PAT. Public repos clone tokenless; set for private repos (`GithubContextProvider` + `GithubWikiBackend`) or higher API rate limits. |
| `REPOS_DIR` | No | Where Scout clones repos. Compose sets `/repos` (the `repos` named volume); local falls back to `.scout/repos`. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | No | Required when `SCOUT_WIKI` or `SCOUT_CONTEXTS` reference `s3:...`. |
| `DB_HOST / PORT / USER / PASS / DATABASE` | No | PostgreSQL config. Compose defaults work locally. |
| `RUNTIME_ENV` | No | `dev` for hot reload (compose sets this); `prd` enables JWT-gated endpoints (requires JWT key env). |

## Conventions

### ContextProvider + WikiBackend

Every external store is either a `ContextProvider` (read-only: `query` + `health` + `get_tools`) or a `WikiBackend` (raw-bytes I/O for the one `WikiContextProvider`). Each provider lives in its own folder under `scout/context/<kind>/` — the class is in `provider.py`, pluggable backends (wiki, web) in `backends/`. Implementation is agentic by default — `.query()` wraps an Agno sub-agent with substrate-specific tools. Each provider exposes its tools via `.get_tools()`; Explorer + Engineer wire them directly (no dispatcher). See [tmp/context_provider.md](tmp/context_provider.md) for the full spec.

### Database

- Use `get_postgres_db()` from the `db` module for agent session storage.
- Use `create_knowledge()` for PgVector hybrid-search knowledge bases.
- Use `get_sql_engine()` for tools that need to write to the `scout` schema (Engineer, migrations). This engine has a guard that rejects writes to `public` / `ai`.
- Use `get_readonly_engine()` for tools that should never write (Explorer, Doctor, Leader). PostgreSQL's `default_transaction_read_only` enforces this at the DB level.
- Knowledge bases use `text-embedding-3-small`.
- `db/tables.py` runs at startup; safe to rerun.

### Imports

```python
from db import db_url, get_postgres_db, create_knowledge, get_sql_engine, get_readonly_engine, SCOUT_SCHEMA
from scout.team import scout
from scout.settings import CONTEXT_DIR, CONTEXT_VOICE_DIR, scout_learnings
from scout.context import ContextProvider, WikiBackend, HealthStatus, HealthState, Entry, Answer, Hit
from scout.context.config import build_wiki, build_contexts, parse_spec
from scout.context.wiki.provider import WikiContextProvider
from scout.tools.ask_context import list_contexts, set_runtime, get_wiki, get_contexts
```
