# Scout: company intelligence

Scout is a **company intelligence agent**: an agent that queries live information sources to assemble context on demand. It follows the "navigation over search" pattern that makes coding agents effective. Instead of fetching chunks from a pre-built vector index, Scout navigates live sources the same way a human would.

Every team eventually battles context sprawl. Knowledge ends up scattered across chat, drives, repos, and wikis, and no one person holds it all in their head. Scout is the teammate who does.

## Quick start

> **Prerequisite:** Docker Desktop installed and running ([install guide](https://docs.docker.com/desktop/)).

```sh
git clone https://github.com/agno-agi/scout && cd scout

cp example.env .env
# set OPENAI_API_KEY in .env

docker compose up -d --build
```

Scout is now running at `http://localhost:8000`.

## Chat with Scout

1. Open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=scout&utm_term=agentos) and log in.
2. Click **Add OS**, choose **Local**, enter **http://localhost:8000**, then **Connect**.
3. Try the pre-configured prompts.

## Chat with Scout in Slack

Scout is designed to live in Slack as your teammate. Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in `.env` and the Slack interface lights up automatically on the next restart. Each Slack thread becomes its own session with conversation history intact.

Step-by-step setup (app manifest, scopes, install flow): [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md).

## How it works

Scout is a single agent with multiple context providers. Each information source (Slack, Drive, CRM, …) becomes a context provider and exposes:

- `query_<source>` — natural-language reads
- `update_<source>` — natural-language writes (where the source supports it)

> *"Find the latest benchmark numbers for model X."* → Scout calls `query_web`, cites sources.
>
> *"Save that as a note."* → Scout calls `update_crm` → the CRM provider's write sub-agent `INSERT`s into `scout.scout_notes`.
>
> *"File a runbook for our incident response."* → Scout calls `update_knowledge` → the wiki provider writes a markdown page under `wiki/knowledge/runbooks/`.
>
> *"Draft a Slack message announcing the launch."* → Scout calls `query_voice` first to load the style guide, then drafts in that voice.

## Contexts

A `ContextProvider` exposes a source to the agent.

| Provider | Trigger | Tools |
|---|---|---|
| **`WebContextProvider`** | always on | `query_web` |
| **`WorkspaceContextProvider`** | always on | `query_workspace` — rooted at the scout repo, so Scout can answer questions about its own codebase |
| **`DatabaseContextProvider`** (CRM) | always on | `query_crm`, `update_crm` — contacts, projects, notes, follow-ups |
| **`WikiContextProvider`** (knowledge) | always on | `query_knowledge`, `update_knowledge` — Scout's prose memory |
| **`WikiContextProvider`** (voice) | always on | `query_voice` — code-managed style guide for emails, Slack, X, long-form |
| **`SlackContextProvider`** | `SLACK_BOT_TOKEN` | `query_slack` — read-only access to messages, channel history, threads, users |
| **`GDriveContextProvider`** | `GOOGLE_SERVICE_ACCOUNT_FILE` | `query_gdrive` — read-only access to files, folders, contents |
| **`MCPContextProvider`** | per-server in [`scout/contexts.py`](scout/contexts.py) | one `query_mcp_<slug>` per registered server (stdio / SSE / streamable-HTTP) |

**Web backends:** `ParallelBackend` (Parallel SDK, when `PARALLEL_API_KEY` is set) or `ParallelMCPBackend` (keyless default).

**Setup guides:** [Slack](docs/SLACK_CONNECT.md) · [Google Drive](docs/GDRIVE_CONNECT.md) · [MCP](docs/MCP_CONNECT.md) · [Git-backed wiki](docs/WIKI_GIT.md)

## Evals

```sh
python -m evals wiring             # code-level invariants (no LLM)
python -m evals                    # behavioral cases, in-process
python -m evals --case <id>        # single case
python -m evals judges             # LLM-scored quality tier
```

See [`docs/EVALS.md`](docs/EVALS.md) for the full picture.

## Deploy

Scout deploys to any Docker-capable host with Postgres. Railway scripts are included for one-command provisioning:

```sh
./scripts/railway/up.sh        # first-time provisioning (Postgres + app service)
./scripts/railway/env.sh       # sync .env to Railway (defaults to .env.production)
./scripts/railway/redeploy.sh  # push a code update
```

Prereqs: [Railway CLI](https://docs.railway.app/guides/cli) + `railway login`.

## Architecture

Built on [Agno](https://github.com/agno-agi/agno) and AgentOS ([docs.agno.com](https://docs.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=scout&utm_term=docs)). Implementation notes: [AGENTS.md](AGENTS.md).