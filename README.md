# Scout

Scout is an **enterprise context agent**. It navigates your company's knowledge through a uniform `Source` protocol: compile dumb stores (local folders, S3 buckets) into a curated wiki; live-read smart sources (Drive, Slack, GitHub) on demand.

Feed it your docs — policies, runbooks, architecture, meeting notes, reports. Scout organizes everything into two layers: a compiled wiki for text-heavy knowledge (concepts, summaries, cross-references) in `context/compiled/`, and a Postgres `scout_knowledge` index that acts as the metadata router across every source. A learning loop in `scout_learnings` compounds every interaction.

Ask a question over Slack, the terminal, or the [AgentOS](https://os.agno.com) web UI. The Leader routes to one of three specialists (Navigator / Researcher / Compiler), each wired to only the tools it needs. The Navigator never reads raw sources — that's the Compiler's job.

## Quick Start

```sh
git clone https://github.com/agno-agi/scout && cd scout
cp example.env .env              # add OPENAI_API_KEY
docker compose up -d --build
```

Confirm Scout is running:

```sh
curl -s http://localhost:8000/manifest | python -m json.tool | head -20
```

You should see `local:raw` + `local:wiki` with `status: connected`. That's a working Scout with nothing configured beyond the model key.

### Connect to the Web UI

1. Open [os.agno.com](https://os.agno.com) and login
2. **Add OS → Local → `http://localhost:8000`**
3. Click **Connect**

## How It Works

Scout is a team of five specialists coordinated by a Leader:

```
Scout (Team Leader — coordinate mode)
├── Navigator    — the workhorse: reads the compiled wiki + live sources,
│                  handles SQL, files, email, calendar, web search
├── Researcher   — gathers sources from the web, saves to context/raw/
│                  (conditional on PARALLEL_API_KEY)
└── Compiler     — iterates compile-on sources, writes Obsidian-compatible
                   markdown to context/compiled/, and runs lint checks
                   (broken backlinks, stale articles, needs_split) after
                   every compile pass
```

### The wiki-first rule

Not every source compiles. Compile only makes sense for stores where the raw form has no good query surface and there's no user edit path that would fight the compiled mirror. **Compile dumb stores. Live-read smart sources.**

| Source | Behaviour | Why |
|---|---|---|
| `LocalFolderSource("./context/raw")` | **compile** → `context/compiled/` | Files have no query surface; wiki is where they become usable |
| `LocalFolderSource("./context/compiled")` | **live-read**, auto-registered | The compile output — this is what Navigator reads |
| `S3Source(bucket=...)` | **compile** → `context/compiled/` | Bucket is a dumb store |
| `GoogleDriveSource(...)` | **live-read** | Drive search is excellent; compiling drifts, users can't edit back |
| `SlackSource(...)` | **live-read** | Threads are the query surface. No meaningful place to "edit" a compiled summary. |
| `GitHubSource(...)` | **live-read** | Grep + git history *is* the query surface. Compiling creates drift with no merge path. |

Every source carries two flags: `compile=True` makes it visible to the Compiler; `live_read=True` makes it visible to the Navigator. The Manifest (rebuilt at startup and every 15 min) enforces both at tool-call time: a Navigator-role `source_read("local:raw", ...)` raises `PermissionError` by contract.

### Execution loop

Every non-greeting interaction:

1. **Classify** — intent + candidate sources from the Manifest.
2. **Recall** — Manifest (free), `scout_knowledge` search, `scout_learnings` search, `context/compiled/index.md`.
3. **Read** — dispatch via the `Source` protocol. Compile-backed content via `context/compiled/`; live sources via `list` / `read` / `find`.
4. **Act** — synthesise; produce drafts only. No sends, no deletions outside `context/raw/`.
5. **Learn** — write `Discovery:` (where the answer lived) and `Retrieval:` (what sequence worked).

## Integrations

Scout boots with local sources on day one. Everything else activates when you add env.

<details>
<summary><strong>Slack</strong> — receive @mentions + post to channels + search threads</summary>

Full setup guide in [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md). Three surfaces, all conditional:

- **Slack Interface** — inbound events. Requires `SLACK_TOKEN` + `SLACK_SIGNING_SECRET`.
- **SlackTools** — Leader posts into channels. Requires `SLACK_TOKEN`.
- **SlackSource** — live-read source for Navigator over threads (capabilities: `LIST`, `READ`, `METADATA`, `FIND_NATIVE`). Requires `SLACK_TOKEN`.

Restrict which channels Scout responds to via `SLACK_CHANNEL_ALLOWLIST` (comma-separated channel IDs). Middleware in `app/main.py` drops events from any other channel.

Each Slack thread maps to a session ID, so every thread gets its own context.

</details>

<details>
<summary><strong>Gmail + Google Calendar + Google Drive</strong></summary>

Full setup in [docs/GOOGLE_AUTH.md](docs/GOOGLE_AUTH.md). One OAuth flow, three services:

- **Gmail** — search, read threads, create drafts. Send is disabled at the code level (`exclude_tools=['send_email','send_email_reply']`).
- **Calendar** — read-only in this build. View events, find available slots. `exclude_tools=['create_event','update_event','delete_event']` + `allow_update=False` on scope.
- **GoogleDriveSource** — live-read source with capabilities `LIST`, `READ`, `METADATA`, `FIND_NATIVE` (Drive's `fullText contains`). Scoped to `GOOGLE_DRIVE_FOLDER_IDS`. Workspace docs (Docs / Sheets) export to markdown / CSV.

All three `GOOGLE_*` env vars must be set together.

</details>

<details>
<summary><strong>GitHub (code search)</strong> — live-read over cloned repos</summary>

`GitHubSource` clones repos into `.scout-cache/repos/<owner>-<repo>/` on first use, debounced fetches every 5 minutes. Capabilities: `LIST`, `READ`, `METADATA`, `FIND_LEXICAL` (ripgrep), `FIND_NATIVE` (REST `search/code` for ad-hoc public repos).

```env
GITHUB_REPOS=acme/api,acme/web
GITHUB_READ_TOKEN=ghp_***
```

Read-only PAT. Scout clones the repos into `.scout-cache/repos/` and ripgreps them in place.

</details>

<details>
<summary><strong>S3 buckets (compile-only)</strong></summary>

Drop PDFs / docs into a bucket, Scout compiles them into the wiki on the next pass.

```env
S3_BUCKETS=acme-docs,acme-archive:reports/
AWS_ACCESS_KEY_ID=AKIA***
AWS_SECRET_ACCESS_KEY=***
AWS_REGION=us-east-1
```

One `S3Source` instance per `bucket[:prefix]`. Compile-only (no live-read) — the Navigator sees compiled articles, not raw S3 objects. Objects over 25 MB skip text extraction and log `skipped-empty`.

</details>

<details>
<summary><strong>Parallel web research</strong> — the single web-search backend</summary>

```env
PARALLEL_API_KEY=***
```

Navigator + Researcher use `parallel_search` + `parallel_extract`. Without this key, Navigator loses web search and the Researcher agent is disabled entirely — the wiki and live sources still work.

</details>

## Example Prompts

```
What does our wiki say about PTO?
Ingest this article: https://arxiv.org/abs/2312.10997
Compile any new sources into the wiki
Lint the wiki — find stale articles and broken backlinks
Push the latest context changes to git
Draft an email to alex@acme.com about the Q2 roadmap
Find the JWT middleware in our acme/api repo
What's in the engineering OKRs doc on Drive?
```

## Scheduled Tasks

| Task | Schedule | Endpoint |
|------|----------|----------|
| Daily Briefing | Weekdays 8 AM | `/teams/scout/runs` |
| Wiki Compile | Every 10 min | `/compile/run` (includes lint pass) |
| Source Health Check | Every 15 min | `/manifest/reload` |
| Inbox Digest | Weekdays 12 PM | `/teams/scout/runs` |
| Learning Summary | Monday 10 AM | `/teams/scout/runs` |
| Weekly Review | Friday 5 PM | `/teams/scout/runs` |

## Architecture

```
AgentOS (app/main.py)  [scheduler=True, tracing=True, GPT-5.4]
 ├── FastAPI / Uvicorn
 ├── Slack Interface (optional)
 ├── Custom router (scout-specific endpoints)
 └── Scout Team (scout/team.py, coordinate mode)
     ├─ Navigator   (scout/agents/navigator.py)
     │  ├─ SQLTools         → PostgreSQL (scout_* tables)
     │  ├─ FileTools        → context/
     │  ├─ ParallelTools    → web search + extraction (conditional)
     │  ├─ GmailTools       → Gmail (drafts only) — conditional
     │  ├─ CalendarTools    → Calendar (read only) — conditional
     │  ├─ source_list / source_read / source_find  [manifest-gated]
     │  ├─ read_manifest
     │  └─ update_knowledge
     ├─ Researcher  (scout/agents/researcher.py) [conditional]
     │  ├─ ParallelTools, FileTools on context/raw/
     │  ├─ ingest_url, ingest_text  → context/raw/<slug>-<short-sha>.md
     │  └─ read_manifest, update_knowledge, source_*
     └─ Compiler    (scout/agents/compiler.py)
        ├─ FileTools (context, no delete)
        ├─ list_compile_sources / compile_one / compile_one_source
        ├─ list_compile_records
        ├─ source_*  [scoped to compile=True sources only]
        └─ runs lint pass after every compile — broken backlinks,
           stale articles, needs_split, user-edit conflicts

     Leader tools: SlackTools (post to channels) [conditional]
     Knowledge:    scout_knowledge (metadata routing)
     Learnings:    scout_learnings (per-user retrieval patterns)
     Manifest:     scout_sources (mirrored in-memory + Postgres)
     Compile state: scout_compiled (source_hash + compiler_output_hash + needs_split)
```

### Sources

| Source | Mode | Enabled by |
|---|---|---|
| `local:raw` — LocalFolderSource(`context/raw`) | compile-only | Always |
| `local:wiki` — LocalFolderSource(`context/compiled`) | live-read | Always |
| `drive` — GoogleDriveSource | live-read | `GOOGLE_DRIVE_FOLDER_IDS` + Google OAuth |
| `slack` — SlackSource | live-read | `SLACK_TOKEN` |
| `github` — GitHubSource | live-read | `GITHUB_REPOS` + `GITHUB_READ_TOKEN` |
| `s3:<bucket>[/<prefix>]` — S3Source | compile-only | `S3_BUCKETS` + `AWS_*` |

## CLI

```sh
python -m scout                       # interactive chat
python -m scout sources               # list registered sources + capabilities
python -m scout manifest              # print the live manifest
python -m scout compile               # compile every compile-on source (skips unchanged)
python -m scout compile --source local:raw --entry handbook.pdf
python -m scout compile --force       # re-compile everything
python -m scout _smoke_gating         # assert Navigator can't read local:raw
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/teams/scout/runs` | POST | Run the Scout team (SSE streaming) |
| `/manifest` | GET | Current manifest |
| `/manifest/reload` | POST | Rebuild manifest from sources |
| `/sources/{id}/health` | GET | Per-source health ping |
| `/compile/run` | POST | Run compile pipeline (no body / `{source_id}` / `{source_id, entry_id}` / `{force: true}`) |
| `/wiki/compile` | POST | Legacy alias for `/compile/run` |
| `/wiki/ingest` | POST | URL or text → `context/raw/` |

## Live Eval Harness

A Docker-hosted test harness is wired into `evals/live/`:

```sh
python -m evals.live run                  # all cases; env-missing ones SKIP
python -m evals.live run --case greeting  # one case
./scripts/eval_loop.sh gating_adversarial # autonomous fix loop (up to 5 attempts)
```

Each case declares its prompt, expected agent, required/forbidden tools, and a single `target_file`. On FAIL the runner writes a rich diagnostic to `evals/results/<case>.md` (failures + member responses + tool calls + docker logs + target file verbatim + directive to Claude Code) so `scripts/eval_loop.sh` can hand it off for autonomous repair.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | **Yes** | — | GPT-5.4 (every agent, Leader, compile runner, eval judge) + `text-embedding-3-small` for Knowledge |
| `PARALLEL_API_KEY` | No | — | Web search + extraction — used by Navigator + Researcher. Without it, the Researcher agent is disabled and Navigator loses web search. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_PROJECT_ID` | No | — | Gmail + Calendar + Drive (all three required together) |
| `GOOGLE_DRIVE_FOLDER_IDS` | No | — | Comma-separated folder IDs — enables `GoogleDriveSource` |
| `SLACK_TOKEN` | No | — | Slack bot token — enables Interface + SlackTools + SlackSource |
| `SLACK_SIGNING_SECRET` | No | — | Required alongside `SLACK_TOKEN` for inbound events |
| `GITHUB_REPOS` | No | — | Comma-separated `owner/repo` — enables `GitHubSource` |
| `GITHUB_READ_TOKEN` | No | — | Read-only PAT for `GitHubSource` |
| `S3_BUCKETS` | No | — | Comma-separated `bucket[:prefix]` — enables `S3Source` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | No | — | Required when `S3_BUCKETS` is set |
| `SCOUT_WORKSPACE_ID` | No | `default` | Workspace scoping (multi-workspace lands later) |
| `SCOUT_API_HOST_PORT` | No | `8000` | Host port the API publishes on |
| `SCOUT_CONTEXT_DIR` / `SCOUT_RAW_DIR` / `SCOUT_COMPILED_DIR` / `SCOUT_VOICE_DIR` | No | — | Override context paths |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE` | No | compose defaults | Postgres |
| `RUNTIME_ENV` | No | — | `dev` for hot reload |

## Troubleshooting

**Navigator answers from `context/raw/` instead of `context/compiled/`**: it shouldn't — `source_read("local:raw", ...)` raises `PermissionError` for any non-Compiler role. Re-run `python -m scout _smoke_gating` — if that PASSes and the Navigator is still leaking, check the diagnostic from `evals/live/`.

**Google token expired**: Google's "Testing" mode expires tokens every 7 days. Re-run `python scripts/google_auth.py` to re-authorize.

**Docker port collision on 5432 / 8000**: set `SCOUT_API_HOST_PORT` in `.env` (or remove the `ports:` entry from `scout-db` if you already have a host Postgres).

**Manifest shows sources `unconfigured`**: the source's env is missing. Check `example.env` for the required set.

**Live eval errors with "Incorrect API key"**: `OPENAI_API_KEY` in `.env` is invalid or rotated. Fix it and `docker compose restart scout-api`.

## Links

- [Agno Docs](https://docs.agno.com)
- [AgentOS Docs](https://docs.agno.com/agent-os/introduction)
- Spec: `tmp/spec.md`
- Pre-build diff: `tmp/spec-diff.md`
