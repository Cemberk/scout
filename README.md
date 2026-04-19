# Scout

Scout is a context agent that answers questions by navigating your team's knowledge in Slack, Drive, GitHub, and local docs.

> **Context Agent:** An agent that navigates sources to assemble context on demand. Unlike retrieval pipelines that fetch chunks from a pre-built index, a Context Agent explores live sources (Slack, Drive, GitHub, docs) the same way a teammate would.

Every team eventually battles context sprawl. Knowledge ends up scattered across chat, drives, repos, and wikis, and no one person holds it all in their head. Scout is the teammate who does.

## Quick start

> **Prerequisite:** Docker Desktop installed and running ([install guide](https://docs.docker.com/desktop/)).

```sh
# Clone and configure
git clone https://github.com/agno-agi/scout && cd scout

# Copy the example.env file and set your OpenAI API key
cp example.env .env

# Run Scout + Postgres
docker compose up -d --build
```

Scout is now running at `http://localhost:8000`.

## Chat with Scout

Scout is designed to live in Slack with your team. But to get started, we can chat with Scout via the web UI:

1. Open [os.agno.com](https://os.agno.com) and log in
2. Click **Add OS**, choose **Local**, enter **http://localhost:8000**, then **Connect**. The web UI is now connected to your Scout running locally on your machine.
3. Click on one of the pre-configured prompts to take Scout for a spin.

## Take Scout for a spin

While Scout gets more useful with more context, it's designed to work out of the box. Walk through the three tiers:

### 1. Ask Scout about anything

Explorer ships with web search built-in (Exa MCP by default; set `PARALLEL_API_KEY` for Parallel), so you can start asking questions immediately with no setup beyond your OpenAI key.

> *Let's chat about Agno. Read the docs at https://docs.agno.com and tell me what it is.*

Explorer fetches the page, reads the sources it finds, and answers with citations.

### 2. Ask Scout about Scout

Scout can navigate codebases. Register any public repo as a context:

```sh
# in .env
SCOUT_CONTEXTS=github:agno-agi/scout
```

Restart `scout-api` and ask:

> *Walk me through how WikiContext turns raw files into a wiki.*

Scout clones the repo on first use and reads the source to answer.

### 3. Give Scout your context

Drop files into `context/raw/` — that's the wiki's input staging area on the default `local:./context` backend. Then tell Engineer to ingest + compile, or run it manually:

```sh
docker exec -it scout-api python -m scout compile
```

Now ask Scout about your own documents.

> *Summarize the key decisions from last week's engineering offsite.*

## Why navigation over search

When you point a coding agent at a codebase, it navigates. It reads the directory structure, follows imports, checks dependencies, builds a map of where things live. The more it explores, the more accurate it gets.

Apply the same pattern to everything else a team knows, and you get a context agent.

The alternative is what most teams already tried: embed every document into a vector store, retrieve chunks at query time, hope the right ones come back. RAG was a breakthrough. It also flattened every source into one interface. Email, docs, Slack, code, all chunked and embedded and searched the same way.

Navigation keeps each source on its own terms. Slack is queried by channel and thread. GitHub is queried by grep and git history. Drive is queried by folder and filename. A SQL database is queried with SQL. Nothing gets flattened.

For the full argument, read [Context Agents: Navigation over Search](https://agno.com/blog/context-agents).

## How it works

Scout splits knowledge into two shapes and runs a four-role team on top.

### Contexts vs the Wiki

| Shape | What it is | Examples |
|---|---|---|
| **Context** (live-read) | Sources queried on their own terms, in place | `LocalContext`, `GithubContext`, `S3Context`, `SlackContext`, `GmailContext`, `DriveContext` |
| **WikiContext** (compile-capable) | One curated store compiled from raw inputs, with a pluggable backend | `LocalBackend` (dev), `GithubBackend` (git-coordinated), `S3Backend` (conditional PUT) |

Both are pre-configured at startup via env:

- `SCOUT_WIKI` — one spec string. Default `local:./context`.
- `SCOUT_CONTEXTS` — comma-separated specs. Empty by default.

Contexts are queried live — nothing is mirrored, nothing drifts. The wiki is the only place compile happens, and its backend handles concurrency (git push rejection, S3 conditional PUT) so multi-container deploys work without coordinating through Scout's process.

### The team

A Leader plus three specialists:

- **Explorer** answers questions by asking the wiki + registered contexts. Read-only SQL on `scout_*` tables. Never writes.
- **Engineer** owns every non-outbound write: `scout_*` tables (DDL + DML scoped to the `scout` schema) and the wiki via `ingest_url` / `ingest_text` / `trigger_compile`.
- **Doctor** diagnoses — `health`, `health_all`, `db_health`, `env_report`. Read-only everywhere; never touches user content.

The **Leader** handles outbound: Slack posting when `SLACK_BOT_TOKEN` is set; Gmail send and Calendar write when `SCOUT_ALLOW_SENDS=true`. The default is drafts-only — the send functions aren't wired to the model. You approve before anything leaves Scout.

Explorer, Engineer, and Doctor share an operational-memory store (`scout_learnings`) — routing hints, corrections, per-user preferences. Written in agentic mode; searched before save so Scout doesn't duplicate.

## Connect your sources

Scout ships with a default local wiki on day one. Each row below activates by adding env + registering a context.

| Integration | Env | Register via | What it does |
|---|---|---|---|
| **Gmail** | `GOOGLE_*` ([setup](docs/GOOGLE_AUTH.md)) + `python scripts/google_auth.py` | `SCOUT_CONTEXTS=gmail` | Search mail, read threads |
| **Google Calendar** | `GOOGLE_*` ([setup](docs/GOOGLE_AUTH.md)) | Leader direct (not a Context) | Read events, find free slots, draft invites |
| **Google Drive** | `GOOGLE_*` ([setup](docs/GOOGLE_AUTH.md)) | `SCOUT_CONTEXTS=drive` | Search files, read Docs/Sheets/Slides |
| **Slack** | `SLACK_BOT_TOKEN` + `SLACK_SIGNING_SECRET` ([setup](docs/SLACK_CONNECT.md)) | `SCOUT_CONTEXTS=slack` | @mention in channels, search threads, Leader posts |
| **GitHub** | built-in (+ optional `GITHUB_ACCESS_TOKEN`) | `SCOUT_CONTEXTS=github:<owner>/<repo>` | Clone + read, grep, git log/blame/diff/show |
| **S3** | `AWS_*` | `SCOUT_CONTEXTS=s3:<bucket>[/<prefix>]` or `SCOUT_WIKI=s3:<bucket>/<prefix>` | Live-read a bucket as a Context, or use S3 as the wiki backend |
| **Local folder** | — | `SCOUT_CONTEXTS=local:<path>` | Any directory you want Explorer to grep/read |
| **Git-hosted wiki** | `GITHUB_ACCESS_TOKEN` (private repos) | `SCOUT_WIKI=github:<owner>/<repo>` | Wiki lives in a git repo — multi-container-safe |
| **Web research** | built-in (Exa MCP, keyless); `PARALLEL_API_KEY` for premium | — | Explorer's web-search fallback |

## Example prompts

```
What does our wiki say about PTO?
Ingest https://arxiv.org/abs/2312.10997 — it's the RAG survey
Find where `Team.coordinate` is defined in agno-agi/agno
Draft an email to alex@acme.com about Q2 roadmap
What's in the engineering OKRs doc on Drive?
Are all my contexts healthy?
```

## CLI

```sh
python -m scout                                       # chat (default)
python -m scout chat                                  # same, explicit
python -m scout contexts                              # wiki + registered contexts + health
python -m scout compile                               # one wiki compile pass
python -m scout compile --force                       # recompile unchanged entries too
```

## API

On top of AgentOS's defaults (`/teams/scout/runs`, `/health`, etc.) the custom endpoints are:

| Endpoint | Method | Purpose |
|---|---|---|
| `/wiki/health` | GET | Wiki health |
| `/wiki/compile` | POST | Run a compile pass (body: `{"force": bool}`) |
| `/wiki/ingest` | POST | Ingest URL / text (body: `{"kind": "url"\|"text", ...}`) |
| `/wiki/query` | POST | Debug: ask the wiki directly |
| `/contexts` | GET | List wiki + every registered context + health |
| `/contexts/{id}/health` | GET | One target's health |
| `/contexts/{id}/query` | POST | Debug: ask one context / wiki |

## Scheduled tasks

No schedules are registered in this build. To run compile on a cadence, either:

- `docker exec -it scout-api python -m scout compile` on a host-side cron, or
- `POST /wiki/compile` from an external scheduler, or
- tell Engineer "compile now" from chat.

A scheduler pod posting to `/wiki/compile` on the API LB is the recommended shape for multi-container deploys.

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | Model and embeddings |
| `SCOUT_WIKI` | No | Wiki backend spec. Default `local:./context`. Prod: `github:<owner>/<repo>` or `s3:<bucket>[/<prefix>]`. |
| `SCOUT_CONTEXTS` | No | Comma-separated live-read context specs. Empty by default. |
| `PARALLEL_API_KEY` | No | Premium web search + URL extraction. Without it, Scout uses Exa's keyless MCP server — research still works. |
| `EXA_API_KEY` | No | Optional. Raises rate limits on the Exa MCP fallback. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_PROJECT_ID` | No | Scout's Google app — Gmail + Calendar + Drive. Drive scope is managed by sharing folders with Scout's account. Run `python scripts/google_auth.py` once to generate `token.json`. |
| `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` | No | Scout's Slack bot (xoxb-…) — interface, SlackTools, and SlackContext |
| `SCOUT_ALLOW_SENDS` | No | `true` to let the Leader actually send Gmail / modify Calendar. Default `false` = drafts-only. |
| `GITHUB_ACCESS_TOKEN` | No | Optional PAT. Public repos clone tokenless; set this for private repos (both `GithubContext` and `GithubBackend`) or to raise the API rate ceiling. |
| `REPOS_DIR` | No | Where Scout clones repos. Compose sets `/repos` (the `repos` named volume); local defaults to `.scout/repos`. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | No | Required when `SCOUT_WIKI` or `SCOUT_CONTEXTS` reference `s3:...`. |
| `DB_*` | No | Postgres (compose defaults work) |

Full list in `example.env`.

## Troubleshooting

- **Google token expired.** Testing-mode OAuth expires every 7 days. Re-run `python scripts/google_auth.py`.
- **`DriveContext` / `GmailContext` report "no Google auth material".** `token.json` isn't present in the container. Run `python scripts/google_auth.py` on the host; the file is bind-mounted in via the `.:/app` volume in `compose.yaml`.
- **Port 5432 or 8000 in use.** Edit the host-side port in `compose.yaml` (e.g. `"8001:8000"`), or drop `ports:` from `scout-db` if Postgres is already on the host.
- **A context shows `disconnected`.** Env missing or wrong. Ask Doctor: `"why is <context id> disconnected?"` — it reads `health` + `env_report` and tells you which var to set.
- **Live response says "Incorrect API key".** `OPENAI_API_KEY` rotated; fix and `docker compose restart scout-api`.

## Architecture

Implementation notes and contribution guide: [CLAUDE.md](CLAUDE.md). Built on Agno and AgentOS: [docs.agno.com](https://docs.agno.com).