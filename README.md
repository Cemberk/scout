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

Scout's Navigator ships with web search built-in (Exa MCP by default; set `PARALLEL_API_KEY` for Parallel), so you can start asking questions immediately with no setup beyond your OpenAI key.

> *Let's chat about Agno. Read the docs at https://docs.agno.com and tell me what it is.*

Navigator fetches the page, reads the sources it finds, and answers with citations.

### 2. Ask Scout about Scout

Scout can navigate codebases, including its own.

> *Let's chat about Scout. Navigate https://github.com/agno-agi/scout and explain how the compiler turns raw files into a wiki.*

Scout reads its own source to answer. You learn what Scout is by watching Scout work.

### 3. Give Scout your context

Drop files into `context/raw/` and Scout will compile them into its wiki. But to start, let's use the sample document: `context/raw/offsite-notes.md`

The compiler runs every hour. But to test the compiler, run it manually:

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

Scout has two execution modes and a team of five specialists.

### Compile vs live-read

Every source Scout connects to is either compiled into a wiki or read live. The choice is per-source and depends on whether the source already has a good query interface.

| Source | Mode | Why |
|---|---|---|
| `./context/raw` (local folder) | compile | Raw files lack structure; compiling gives them one |
| `./context/compiled` (local folder) | live-read | The compiled wiki itself |
| S3 bucket | compile | Bucket listings are flat; compiling adds structure |
| Google Drive | live-read | Drive search is already good |
| Slack | live-read | Threads *are* the query surface |
| GitHub | live-read | Grep and git history *are* the query surface |

Compiled sources get turned into a cross-linked markdown wiki that lives in `context/compiled/`. Live sources get queried in place. No mirror, no drift.

### The team

Five specialists coordinated by a Leader:

- **Navigator** answers the question. Read-only everywhere: compiled wiki, live sources (Drive/Slack/Gmail inbox/Calendar), SQL SELECT, web search. Never writes.
- **Compiler** owns every wiki write path. Ingests URLs and text into `context/raw/`, compiles into `context/compiled/`, lints for broken backlinks and stale articles after each pass.
- **CodeExplorer** clones any git repo on demand into `$REPOS_DIR` and answers code questions (grep, read, blame, log). Read-only.
- **Engineer** owns SQL writes. Creates `scout_*` tables on demand, inserts user-provided notes / facts / contacts / decisions, records every schema change back to Knowledge so Navigator can find it.
- **Doctor** diagnoses Scout's own health (sources, compile state, env) and self-heals via retry / reload / refresh / cache-clear. Never touches user data.

The **Leader** handles all outbound: Slack posting when `SLACK_BOT_TOKEN` is set; Gmail send and Calendar write when `SCOUT_ALLOW_SENDS=true`. The default is drafts-only — the send functions aren't even wired to the model. You approve before anything leaves Scout.

## Connect your sources

Scout ships with local folders on day one. Each row below activates when you add the env.

| Integration | Env | What it does |
|---|---|---|
| **Gmail + Calendar + Drive** | `GOOGLE_*` ([setup](docs/GOOGLE_AUTH.md)) | Search mail, draft replies, read events, query Drive |
| **Slack** | `SLACK_BOT_TOKEN` + `SLACK_SIGNING_SECRET` ([setup](docs/SLACK_CONNECT.md)) | @mention in channels, search threads, post |
| **Code exploration** | built-in (+ optional `GITHUB_ACCESS_TOKEN`) | `CodeExplorer` clones any public repo on demand and answers code questions — grep, read, blame, log. Add a PAT for private repos or higher rate limits. |
| **S3** | `S3_BUCKETS` + `AWS_*` | Compile PDFs and docs from buckets into the wiki |
| **Web research** | built-in (Exa MCP, keyless); `PARALLEL_API_KEY` for premium | Web search + URL extraction. Scout ships with Exa MCP so research works on day one; set `PARALLEL_API_KEY` to switch to Parallel for better extraction and higher rate limits. |

## Example prompts

```
What does our wiki say about PTO?
Ingest https://arxiv.org/abs/2312.10997
Find where `Team.coordinate` is defined in agno-agi/agno
Draft an email to alex@acme.com about Q2 roadmap
What's in the engineering OKRs doc on Drive?
```

## CLI

```sh
python -m scout                       # chat
python -m scout sources               # registered sources + capabilities
python -m scout manifest              # live manifest
python -m scout compile               # compile new or changed inputs
python -m scout compile --force       # re-compile everything
```

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/teams/scout/runs` | POST | Run Scout (SSE streaming) |
| `/manifest` | GET | Current manifest |
| `/manifest/reload` | POST | Rebuild manifest |
| `/sources/{id}/health` | GET | Per-source health ping |
| `/compile/run` | POST | Run compile pass |
| `/wiki/ingest` | POST | URL or text → `context/raw/` |
| `/doctor/run` | POST | Doctor diagnostic pass (returns JSON report) |
| `/doctor/health` | GET | Liveness probe |

## Scheduled tasks

Compile runs every hour. Source health refresh every 15 minutes. Scout also sends a weekday 8 AM briefing, a noon inbox digest, a Monday learning summary, and a Friday review. Configurable in `app/main.py`.

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | Model and embeddings |
| `PARALLEL_API_KEY` | No | Premium web search + URL extraction. Without it, Scout uses Exa's keyless MCP server — research still works. |
| `EXA_API_KEY` | No | Optional. Raises rate limits on the Exa MCP fallback; not needed to use it. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_PROJECT_ID` | No | Scout's own Google app — Gmail + Calendar + Drive. Drive scope is managed by sharing folders with Scout's account. |
| `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` | No | Scout's own Slack bot (xoxb-…) — interface and source |
| `SCOUT_ALLOW_SENDS` | No | `true` to let the Leader actually send Gmail / modify Calendar. Default `false` = drafts-only. |
| `GITHUB_ACCESS_TOKEN` | No | Optional PAT for CodeExplorer. Public repos clone tokenless; set this for private repos or to raise the API rate ceiling. |
| `REPOS_DIR` | No | Where CodeExplorer clones repos. Compose sets `/repos` (the `repos` named volume); local defaults to `.scout/repos`. |
| `S3_BUCKETS` / `AWS_*` | No | S3 compile |
| `DB_*` | No | Postgres (compose defaults work) |

Full list in `example.env`.

## Troubleshooting

- **Google token expired.** Testing-mode OAuth expires every 7 days. Re-run `python scripts/google_auth.py`.
- **Port 5432 or 8000 in use.** Edit the host-side port in `compose.yaml` (e.g. change `"8000:8000"` to `"8001:8000"`), or drop `ports:` from `scout-db` if Postgres is already running on the host.
- **Source shows `unconfigured`.** Env missing; check `example.env`.
- **Live eval says "Incorrect API key".** `OPENAI_API_KEY` rotated; fix and `docker compose restart scout-api`.

## Architecture

Implementation notes and contribution guide: [CLAUDE.md](CLAUDE.md). Built on Agno and AgentOS: [docs.agno.com](https://docs.agno.com).