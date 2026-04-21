# CLAUDE.md

## Project Overview

Scout is an **enterprise context agent** — a four-role team coordinated by a Leader, built on top of the `ContextProvider` base class. This release is a **web-only thin slice**: the only shipping context is `WebContextProvider`. Filesystem / GitHub / Slack / Gmail / Drive / wiki land in subsequent milestones.

## Architecture

```
Scout (Team Leader — coordinate mode, pure router, no tools)
├── Explorer  — answers questions by asking the registered contexts.
│               SQL read-only (scout_* tables). Shares scout_learnings.
├── Engineer  — owns SQL writes into scout_* tables (DDL + DML in the
│               scout schema). Shares scout_learnings.
└── Doctor    — diagnoses health: contexts, DB, env. Read-only
                everywhere. Shares scout_learnings.
```

## ContextProvider

`scout/context/provider.py` defines the base. Every external source subclasses `ContextProvider` and implements:

- `query(question, *, limit) -> Answer` — natural-language access
- `status() -> Status` — is the source reachable?

`mode` controls how the provider surfaces itself to the calling agent:

| Mode | Exposure |
|---|---|
| `default` | The provider's recommended exposure. Each subclass decides. |
| `agent` | One `query_<id>` tool wrapping a sub-agent. |
| `tools` | The underlying tools directly. |

`model` swaps the model used by the internal sub-agent (when one is built). `instructions()` returns mode-aware usage guidance for the calling agent.

The full type set:
- `Status(ok: bool, detail: str = "")`
- `Document(id, name, uri=None, kind="file", snippet=None)` — a piece of content
- `Answer(results: list[Document] = [], text: str | None = None)` — what `query()` returns

## One write surface

| Write surface | Owner | Call |
|---|---|---|
| `scout_*` user-data tables | Engineer | SQL DDL + DML, scoped to the `scout` schema (write guard + `get_sql_engine()`) |

Everything else reads. Explorer and Doctor use `get_readonly_engine()` (PostgreSQL's `default_transaction_read_only`). The scout engine has a `before_cursor_execute` hook that rejects any DDL/DML targeting `public` or `ai`.

## Structure

```
scout/
├── __init__.py
├── __main__.py                     # CLI: chat | contexts
├── team.py                         # Leader + three specialists, coordinate mode
├── settings.py                     # DB-dependent runtime objects
├── contexts.py                     # build_contexts() + registry (set_runtime / get_contexts / list_contexts)
├── agents/
│   ├── explorer.py                 # per-provider query_* + list_contexts + read-only SQL
│   ├── engineer.py                 # SQL writes + introspect + reasoning + learnings
│   └── doctor.py                   # status / status_all / db_status / env_report
├── context/                        # The library — ships to agno.context
│   ├── __init__.py
│   ├── _utils.py                   # answer_from_run
│   ├── mode.py                     # ContextMode enum
│   ├── provider.py                 # ContextProvider ABC + Status/Document/Answer
│   └── web/
│       ├── __init__.py
│       ├── backend.py              # WebBackend Protocol
│       ├── provider.py             # WebContextProvider
│       └── backends/
│           ├── __init__.py
│           ├── exa_mcp.py          # ExaMCPBackend (keyless Exa MCP)
│           └── parallel.py         # ParallelBackend (parallel-web SDK)
└── tools/
    ├── diagnostics.py              # status / status_all / db_status / env_report (Doctor)
    ├── introspect.py               # introspect_schema (Engineer)
    └── learnings.py                # create_update_learnings (all three specialists)

app/
├── main.py                         # AgentOS entry (lifespan wires contexts)
├── router.py                       # /contexts/* endpoints
└── config.yaml

db/
├── session.py                      # get_sql_engine (guarded) / get_readonly_engine
├── url.py                          # DB URL builder
└── tables.py                       # Canonical DDL: scout_contacts / projects / notes.

evals/
├── cases.py                        # Behavioral Case dataclass + CASES tuple
├── runner.py                       # In-process + SSE transports + fixtures
├── wiring.py                       # Code-level invariants (no LLM)
├── judges.py                       # LLM-scored quality tier
└── __main__.py                     # CLI dispatch
```

## Commands

```bash
./scripts/venv_setup.sh && source .venv/bin/activate
./scripts/format.sh                   # Format code
./scripts/validate.sh                 # ruff + mypy + wiring invariants

# CLI
python -m scout                       # Chat
python -m scout contexts              # List contexts + status

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

Secrets live in `.env`. Anything that hits OpenAI / Parallel / Exa from the host (`python -m evals`, etc.) needs `.env` loaded:

1. **Prefer direnv:** `direnv allow .` once per repo.
2. **Fallback:** `set -a; source .env; set +a; python -m evals`
3. **Per-invocation (Bash tool):** `set -a && source .env && set +a && ...`

Docker picks up `.env` automatically via `docker compose`, so code inside `scout-api` has everything. Only direct host-shell invocations need the explicit source.

## Contexts

`scout/contexts.py::build_contexts()` is the env-driven factory called once at startup. The web provider is on by default.

| Backend selection | Trigger |
|---|---|
| `ParallelBackend` | `PARALLEL_API_KEY` set |
| `ExaMCPBackend` | otherwise (keyless) |

## User Data Tables

Shipped tables under the `scout` schema (created on first startup via `db/tables.py`). All carry `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ DEFAULT NOW()`.

| Table | Purpose | Domain columns |
|---|---|---|
| `scout_contacts` | People | `name`, `emails TEXT[]`, `phone`, `tags TEXT[]`, `notes` |
| `scout_projects` | Things in motion | `name`, `status`, `tags TEXT[]` |
| `scout_notes` | Free-form notes | `title`, `body`, `tags TEXT[]`, `source_url` |

Beyond these three, Engineer creates new `scout_*` tables on demand — always in the `scout` schema, always with the standard columns, always recording the new shape into `scout_learnings` afterward.

## Learnings

One operational-memory store: `scout_learnings`. Explorer, Engineer, Doctor all attach it as their `LearningMachine`'s knowledge base in agentic mode. Routing hints, corrections, per-user preferences — Scout's memory *about itself*. `update_learnings(note, title=?)` writes; the LearningMachine searches before saving so duplicates don't pile up.

## Tools by Agent

| Agent | Tools |
|-------|-------|
| Explorer | `SQLTools` (**read-only engine**, `scout` schema), `query_<id>` (one per registered provider via `provider.get_tools()`), `list_contexts`, `update_learnings` |
| Engineer | `SQLTools` (scout engine, **schema-guarded** to `scout`), `introspect_schema`, `update_learnings`, `ReasoningTools` |
| Doctor | `SQLTools` (**read-only**), `status`, `status_all`, `db_status`, `env_report`, `update_learnings` |
| Leader | (none — pure router) |

**Per-provider tools are built by the registry.** `scout.contexts.set_runtime(contexts)` installs the singleton list and rewires Explorer's `.tools` list in one call. The app lifespan calls it once at startup; eval fixtures call it per case.

## API Endpoints

On top of AgentOS's defaults (`/teams/scout/runs`, `/health`, …):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/contexts` | GET | List every registered context + status |
| `/contexts/{id}/status` | GET | One context's status |
| `/contexts/{id}/query` | POST | Debug: ask one context directly |

## Model

Every agent and the Leader run on `OpenAIResponses(id="gpt-5.4")` via `agno.models.openai`. The literal sits at each call site. OpenAI is also what `text-embedding-3-small` uses for the Learnings PgVector path, so one key covers everything.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **Yes** | GPT-5.4 for every agent + embeddings for Learnings |
| `PARALLEL_API_KEY` | No | Premium web research for `WebContextProvider`. When set, Scout swaps to `ParallelBackend`; otherwise the default is keyless `ExaMCPBackend`. |
| `EXA_API_KEY` | No | Optional. Raises rate limits on `ExaMCPBackend`; not required. |
| `DB_HOST / PORT / USER / PASS / DATABASE` | No | PostgreSQL config. Compose defaults work locally. |
| `RUNTIME_ENV` | No | `dev` for hot reload (compose sets this); `prd` enables JWT-gated endpoints. |

## Conventions

### ContextProvider

Every external source subclasses `ContextProvider` (in `scout/context/provider.py`). Each provider lives in its own folder under `scout/context/<kind>/` — the class is in `provider.py`, pluggable backends in `backends/`. Implementation is agentic by default — `_build_agent()` wraps a sub-agent with backend tools when needed (lazy). Each provider exposes its tools via `.get_tools()`; Explorer wires them directly.

### Database

- Use `get_postgres_db()` from the `db` module for agent session storage.
- Use `create_knowledge()` for PgVector hybrid-search knowledge bases.
- Use `get_sql_engine()` for tools that need to write to the `scout` schema (Engineer, migrations). This engine has a guard that rejects writes to `public` / `ai`.
- Use `get_readonly_engine()` for tools that should never write (Explorer, Doctor). PostgreSQL's `default_transaction_read_only` enforces this at the DB level.
- Knowledge bases use `text-embedding-3-small`.
- `db/tables.py` runs at startup; safe to rerun.

### Imports

```python
from db import db_url, get_postgres_db, create_knowledge, get_sql_engine, get_readonly_engine, SCOUT_SCHEMA
from scout.team import scout
from scout.settings import scout_learnings
from scout.contexts import build_contexts, get_contexts, list_contexts, set_runtime
from scout.context import ContextProvider, ContextMode, Answer, Document, Status
from scout.context.web import WebContextProvider, WebBackend
from scout.context.web.backends import ExaMCPBackend, ParallelBackend
```
