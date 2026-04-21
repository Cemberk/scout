# Scout

Scout is a context agent — an agent that explores information sources and assembles context on demand.

Unlike retrieval pipelines that fetch chunks from a pre-built index, a Context Agent explores live sources the same way a human would.

Every team eventually battles context sprawl. Knowledge ends up scattered across chat, drives, repos, and wikis, and no one person holds it all in their head. Scout is the teammate who does.

## Quick start

> **Prerequisite:** Docker Desktop installed and running ([install guide](https://docs.docker.com/desktop/)).

```sh
git clone https://github.com/agno-agi/scout && cd scout
cp example.env .env             # set OPENAI_API_KEY in .env
docker compose up -d --build
```

Scout is now running at `http://localhost:8000`.

## Chat with Scout

1. Open [os.agno.com](https://os.agno.com) and log in.
2. Click **Add OS**, choose **Local**, enter **http://localhost:8000**, then **Connect**.
3. Try the pre-configured prompts.

## How it works

Scout is a four-role team:

- **Leader** — pure router. Routes intent to the right specialist; never holds tools itself.
- **Explorer** — read-only question answering via the registered contexts + read-only SQL on `scout_*` tables.
- **Engineer** — owns SQL writes into the `scout` schema (DDL + DML).
- **Doctor** — diagnoses Scout's own health: `status`, `status_all`, `db_status`, `env_report`. Read-only.

Explorer, Engineer, and Doctor share an operational-memory store (`scout_learnings`) — routing hints, corrections, per-user preferences. Searched before save so duplicates don't pile up.

## Contexts

A `ContextProvider` exposes a source to the team. Each provider has a `mode`:

| Mode | What it exposes |
|---|---|
| `default` | The provider's recommended exposure (each subclass picks). |
| `agent` | Wraps the provider behind a sub-agent; one `query_<id>` tool. |
| `tools` | Exposes the underlying tools directly. |

This release ships **`WebContextProvider`** with two backends:

- **`ExaMCPBackend`** — keyless web research via Exa's public MCP server (default).
- **`ParallelBackend`** — premium research + extraction; activates when `PARALLEL_API_KEY` is set.

Web's default mode is `tools` — the calling agent gets `web_search` / `web_extract` (or the Exa-named equivalents) directly.

## Engineer's tables

Shipped in the `scout` schema, created on first startup:

- `scout_contacts` — `name, emails[], phone, tags[], notes`
- `scout_projects` — `name, status, tags[]`
- `scout_notes` — `title, body, tags[], source_url`

Every table carries `id SERIAL PK`, `user_id TEXT NOT NULL`, `created_at TIMESTAMPTZ`.

## CLI

```sh
python -m scout                    # interactive chat
python -m scout contexts           # list registered contexts + status
```

## API

On top of AgentOS's defaults (`/teams/scout/runs`, `/health`):

| Endpoint | Method | Purpose |
|---|---|---|
| `/contexts` | GET | List every registered context + status |
| `/contexts/{id}/status` | GET | One context's status |
| `/contexts/{id}/query` | POST | Debug: ask one context directly |

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | Model and embeddings |
| `PARALLEL_API_KEY` | No | Premium web research + URL extraction. Without it, Scout uses Exa's keyless MCP. |
| `EXA_API_KEY` | No | Optional. Raises rate limits on the Exa MCP fallback. |
| `DB_*` | No | Postgres (compose defaults work) |

Full list in [`example.env`](example.env).

## Evals

```sh
python -m evals wiring             # code-level invariants (no LLM)
python -m evals                    # behavioral cases, in-process
python -m evals --case <id>        # single case
python -m evals --live             # SSE against a running scout-api
python -m evals judges             # LLM-scored quality tier
```

See [`docs/EVALS.md`](docs/EVALS.md) for the full picture.

## Troubleshooting

- **Port 5432 or 8000 in use.** Edit the host-side port in `compose.yaml`.
- **A context shows down.** Ask Doctor: `"why is web disconnected?"` — it reads `status` + `env_report`.
- **"Incorrect API key".** `OPENAI_API_KEY` rotated; fix and `docker compose restart scout-api`.

## Architecture

Implementation notes: [CLAUDE.md](CLAUDE.md). Built on Agno and AgentOS: [docs.agno.com](https://docs.agno.com).
