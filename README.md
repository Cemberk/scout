# Scout

Scout is a **context agent**: an agent that queries information sources to assemble context on demand. It follows the "navigation over search" pattern that makes coding agents so effective: instead of fetching chunks from a pre-built vector index, Scout navigates live sources the same way a human would.

Every team eventually battles context sprawl. Knowledge ends up scattered across chat, drives, repos, and wikis, and no one person holds it all in their head. Scout is the teammate who does.

Scout is built around a small `ContextProvider` abstraction — any source is just a subclass. Today ships providers for the **web**, **local filesystem**, **Slack**, **Google Drive**, a **CRM** (contacts / projects / notes / follow-ups, stored in Postgres), a writable **knowledge wiki** (Scout files prose pages — runbooks, design notes, learnings — as it learns), a read-only **voice wiki** (the company style guide for external content, code-managed), and any **MCP server** (wire one up in [`scout/contexts.py`](scout/contexts.py) and it becomes its own `query_mcp_<slug>` tool). GitHub, Gmail, and Calendar land in the next release.

## Quick start

> **Prerequisite:** Docker Desktop installed and running ([install guide](https://docs.docker.com/desktop/)).

```sh
git clone https://github.com/agno-agi/scout && cd scout
cp example.env .env             # set OPENAI_API_KEY in .env
docker compose up -d --build
```

Scout is now running at `http://localhost:8000`.

## Chat with Scout

1. Open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=scout&utm_term=agentos) and log in.
2. Click **Add OS**, choose **Local**, enter **http://localhost:8000**, then **Connect**.
3. Try the pre-configured prompts.

## Chat with Scout in Slack

Scout can live in Slack as a teammate. Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in `.env` and the Slack interface lights up automatically on the next restart. Each Slack thread becomes its own session with conversation history intact.

Step-by-step setup (app manifest, scopes, install flow): [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md).

## How it works

Scout is a single agent with N context providers. One LLM hop per turn — no router, no specialists. Every source (web, files, Slack, Drive, the user's own CRM) is a `ContextProvider` that surfaces namespaced tools on Scout.

> *"Find the latest benchmark numbers for model X."* → Scout calls `web_search`, cites sources.
>
> *"Save that as a note."* → Scout calls `update_crm` → the CRM provider's write sub-agent `INSERT`s into `scout.scout_notes`.
>
> *"File a runbook for our incident response."* → Scout calls `update_knowledge` → the wiki provider writes a markdown page under `wiki/knowledge/runbooks/`.
>
> *"Draft a Slack message announcing the launch."* → Scout calls `query_voice` first to load the style guide, then drafts in that voice.

## Contexts

A `ContextProvider` exposes a source to the team. Each provider has a `mode`:

| Mode | What it exposes |
|---|---|
| `default` | The provider's recommended exposure (each subclass picks). |
| `agent` | Wraps the provider behind a sub-agent; one `query_<id>` tool. |
| `tools` | Exposes the underlying tools directly. |

### Ships today

| Provider | Env trigger | What it exposes |
|---|---|---|
| **`WebContextProvider`** | always on — picks a backend based on keys below | `web_search` / `web_extract` |
| **`WorkspaceContextProvider`** | always on — rooted at the scout repo (see `SCOUT_FS_ROOT` in [`scout/contexts.py`](scout/contexts.py)), so Scout can answer questions about its own codebase | one `query_workspace` tool routed through a tuned read-only sub-agent (lists, searches, and reads files; common dependency / build / cache directories excluded) |
| **`DatabaseContextProvider`** (CRM) | always on — Postgres via `DB_*` | `query_crm` reads the user's contacts / projects / notes / follow-ups; `update_crm` saves or modifies them. Two internal sub-agents so the read path never sees the write engine; writes are scoped to the `scout` schema and guarded at the engine layer. |
| **`WikiContextProvider`** (knowledge) | always on — rooted at `wiki/knowledge/` (gitignored) | `query_knowledge` / `update_knowledge` — Scout's prose memory. Filesystem-backed by default; flip to `GitBackend` for durability + audit trail (see [`docs/WIKI_GIT.md`](docs/WIKI_GIT.md)). |
| **`WikiContextProvider`** (voice) | always on — rooted at `wiki/voice/` (committed) | `query_voice` only (`write=False`) — code-managed style guide for emails, Slack messages, X posts, and long-form docs. |
| **`SlackContextProvider`** | `SLACK_BOT_TOKEN` | read-only `search_workspace` / `get_channel_history` / `get_thread` / `list_users`. Sending is disabled — post via the Slack interface instead. Setup: [`docs/SLACK_CONNECT.md`](docs/SLACK_CONNECT.md). |
| **`GDriveContextProvider`** | `GOOGLE_SERVICE_ACCOUNT_FILE` | read-only `search_files` / `list_files` / `read_file`. Scout authenticates as its own service account — share folders with the SA email to grant access. Setup: [`docs/GDRIVE_CONNECT.md`](docs/GDRIVE_CONNECT.md) (or `./scripts/google_setup.sh` for the automated path). |
| **`MCPContextProvider`** | wired in [`scout/contexts.py`](scout/contexts.py) | Wraps any MCP server (stdio / SSE / streamable-HTTP). One `query_mcp_<slug>` tool on Scout per server; sub-agent instructions built dynamically from `list_tools()`. Setup: [`docs/MCP_CONNECT.md`](docs/MCP_CONNECT.md). |

**Web backends**:

- **`ParallelBackend`** — premium research + extraction via the Parallel SDK. Activates when `PARALLEL_API_KEY` is set.
- **`ParallelMCPBackend`** — keyless web research via Parallel's public MCP server (`web_search` + `web_fetch`). Default when no key is set.

### Add your own

Subclass `ContextProvider`, implement four methods, register it in [`scout/contexts.py`](scout/contexts.py):

```python
from agno.context import Answer, ContextProvider, Status
from agno.run import RunContext

class MyProvider(ContextProvider):
    def status(self) -> Status: ...
    async def astatus(self) -> Status: ...
    def query(self, question: str, *, run_context: RunContext | None = None) -> Answer: ...
    async def aquery(self, question: str, *, run_context: RunContext | None = None) -> Answer: ...
```

See [`agno.context.web.provider`](https://github.com/agno-agi/agno/blob/main/libs/agno/agno/context/web/provider.py) for a worked example.

## Storage

Scout writes user data to `scout_*` tables, created on first startup:

- `scout_contacts` — people (`name, emails[], phone, tags[], notes`)
- `scout_projects` — things in motion (`name, status, tags[]`)
- `scout_notes` — free-form notes (`title, body, tags[], source_url`)
- `scout_followups` — things to come back to (`title, notes, due_at, status, tags[]`)

All tables carry `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ`. The CRM provider's write sub-agent creates new `scout_*` tables on demand when intent doesn't fit an existing one.

## CLI

```sh
python -m scout                    # interactive chat
python -m scout contexts           # list registered contexts + status
```

Host-shell invocations need `.env` loaded — `direnv allow .` once, or `set -a; source .env; set +a` per shell.

## API

On top of AgentOS's defaults (`/agents/scout/runs`, `/health`):

| Endpoint | Method | Purpose |
|---|---|---|
| `/contexts` | GET | List every registered context + status |
| `/contexts/{id}/status` | GET | One context's status |
| `/contexts/{id}/query` | POST | Debug: ask one context directly |

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | Model and embeddings |
| `PARALLEL_API_KEY` | No | Selects `ParallelBackend` (Parallel SDK). Without it, web falls back to `ParallelMCPBackend` (keyless). |
| `SLACK_BOT_TOKEN` | No | Bot User OAuth Token. Pair with `SLACK_SIGNING_SECRET` for the Slack interface; alone, activates the Slack context provider. |
| `SLACK_SIGNING_SECRET` | No | Slack signing secret for request verification. |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | No | Path to Scout's Google service-account JSON key. Activates the Drive context provider. |
| `DB_*` | No | Postgres (compose defaults work) |
| `RUNTIME_ENV` | No | `dev` for hot reload (compose sets this); `prd` enables JWT-gated endpoints. |
| `AGENTOS_URL` | No | Scheduler base URL. Defaults to `http://127.0.0.1:8000`. |

Full list in [`example.env`](example.env).

## Evals

```sh
python -m evals wiring             # code-level invariants (no LLM)
python -m evals                    # behavioral cases, in-process
python -m evals --case <id>        # single case
python -m evals judges             # LLM-scored quality tier
```

See [`docs/EVALS.md`](docs/EVALS.md) for the full picture.

## Deploy

Any Docker-capable host with a Postgres addon works. Railway scripts are included for one-command deployment:

```sh
./scripts/railway/up.sh        # first-time provisioning (Postgres + app service)
./scripts/railway/env.sh       # sync .env to Railway (defaults to .env.production)
./scripts/railway/redeploy.sh  # push a code update
```

Prereqs: [Railway CLI](https://docs.railway.app/guides/cli) + `railway login`.

## Architecture

Built on [Agno](https://github.com/agno-agi/agno) and AgentOS ([docs.agno.com](https://docs.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=scout&utm_term=docs)). Implementation notes: [AGENTS.md](AGENTS.md).
