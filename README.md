# Scout

Scout is a **context agent** — an agent that explores information sources and assembles context on demand. It follows the "navigation over search" pattern that makes coding agents so effective: instead of fetching chunks from a pre-built index, Scout queries live sources the way a human would.

Every team eventually battles context sprawl. Knowledge ends up scattered across chat, drives, repos, and wikis, and no one person holds it all in their head. Scout is the teammate who does.

Scout is built around a small `ContextProvider` abstraction — any source is just a subclass. Today ships providers for the **web**, **local filesystem**, **Slack**, **Google Drive**, a **CRM** (the user's own contacts / projects / notes, stored in Postgres), and any **MCP server** (wire one up in [`scout/contexts.py`](scout/contexts.py) and it becomes its own `query_mcp_<slug>` tool). GitHub, Gmail, and Calendar land in the next release.

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
| **`FilesystemContextProvider`** | always on — rooted at the scout repo (see `FS_ROOT` in [`scout/contexts.py`](scout/contexts.py)) | read-only `list_files` / `search_files` (glob) / `search_content` / `read_file` |
| **`DatabaseContextProvider`** (CRM) | always on — Postgres via `DB_*` | `query_crm` reads the user's contacts / projects / notes; `update_crm` saves or modifies them. Two internal sub-agents so the read path never sees the write engine; writes are scoped to the `scout` schema and guarded at the engine layer. |
| **`SlackContextProvider`** | `SLACK_BOT_TOKEN` | read-only `search_workspace` / `get_channel_history` / `get_thread` / `list_users`. Sending is disabled — post via the Slack interface instead. Setup: [`docs/SLACK_CONNECT.md`](docs/SLACK_CONNECT.md). |
| **`GDriveContextProvider`** | `GOOGLE_SERVICE_ACCOUNT_FILE` | read-only `search_files` / `list_files` / `read_file`. Scout authenticates as its own service account — share folders with the SA email to grant access. Setup: [`docs/GDRIVE_CONNECT.md`](docs/GDRIVE_CONNECT.md) (or `./scripts/google_setup.sh` for the automated path). |
| **`MCPContextProvider`** | wired in [`scout/contexts.py`](scout/contexts.py) | Wraps any MCP server (stdio / SSE / streamable-HTTP). One `query_mcp_<slug>` tool on Scout per server; sub-agent instructions built dynamically from `list_tools()`. Setup: [`docs/MCP_CONNECT.md`](docs/MCP_CONNECT.md). |

**Web backends**, first-match selection:

- **`ParallelBackend`** — premium research + extraction. Activates when `PARALLEL_API_KEY` is set.
- **`ExaBackend`** — Exa SDK path (search + contents). Activates when `EXA_API_KEY` is set.
- **`ExaMCPBackend`** — keyless web research via Exa's public MCP server. Default when neither key is set.

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
| `PARALLEL_API_KEY` | No | Premium web research + URL extraction. Selects `ParallelBackend`. |
| `EXA_API_KEY` | No | Selects `ExaBackend` (Exa SDK path). Ignored if `PARALLEL_API_KEY` is set. |
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

Built on [Agno](https://github.com/agno-agi/agno) and AgentOS ([docs.agno.com](https://docs.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=scout&utm_term=docs)). Implementation notes: [CLAUDE.md](CLAUDE.md).
