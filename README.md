# Scout: company intelligence agent

Scout is an open-source company intelligence agent. It navigates live information sources (web, slack, drive, wiki, CRM, MCP servers) to assemble context on demand - and builds its own wiki and CRM as it learns about your company.

YC's Summer 2026 RFS named "Company Brain" and "AI Operating System for Companies" — the same idea from two angles: pull knowledge out of fragmented sources and turn it into something AI can act on. The brain is the data layer. The OS runs on top of it. Neither exists as a finished product today, but the pieces do.

Scout stitches them together using patterns that already work: **navigation over search**, **context providers**, agentic SQL, and persistent memory.

**Navigation over search.** The default move when working with knowledge sources is to ingest everything into a vector db, chunk, embed, and pray. The index is always stale. Chunks split at the wrong boundaries. Citations point at fragments that were true last Tuesday. Half the time the relevant content was a Slack thread that never got indexed because nobody indexes Slack. Coding agents figured this out — they don't search, they navigate: `ls`, `grep`, open the file, follow the import. Scout does the same thing across Slack, Drive, and the rest.

**Scout also builds its own CRM.** Some things don't have a natural source home. *"Josh from Anthropic shared a new RLM paper"* — that lives nowhere obvious. Scout adds Josh to the CRM, parses the paper into the wiki, and links them.

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

Scout is designed to live in Slack as your teammate. Follow [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md) to add Scout to your slack workspace.

## How it works

Scout is a single agent with many context providers. Each information source becomes a provider and exposes two natural-language tools to Scout:

- `query_<source>` — reads
- `update_<source>` — writes (when supported)

This thin layer solves three problems that hit any agent with a real tool surface: context pollution from too many tools, degrading performance from overlapping scopes, and the main agent forgetting its job because its context is all tool quirks.

The win isn't fewer tools — it's that **a sub-agent behind each provider owns the source's quirks**. Scout sees `query_slack`. Behind it, a sub-agent knows to look up the user before DMing, paginate by cursor, and prefer `conversations.replies` for threads. Scout's context never sees any of that. (And no, [skills](https://www.anthropic.com/news/skills) don't solve this: skills load task instructions on-demand, but the tools still land on the main agent and intermediate tool results still land in the main context.)

> *"Find the latest benchmark numbers for model X."* → `query_web`, cites sources.
>
> *"Save that as a note."* → `update_crm` → write sub-agent `INSERT`s into `scout.scout_notes`.
>
> *"File a runbook for incident response."* → `update_knowledge` → wiki sub-agent writes a markdown page under `wiki/knowledge/runbooks/`.
>
> *"Track my coffee consumption — flat white, extra shot."* → `update_crm` → write sub-agent creates `scout.scout_coffee_orders` and inserts the row. Schema on demand.
>
> *"Draft a Slack message announcing the launch."* → `query_voice` first to load the style guide, then drafts in that voice.

## Context Providers

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

The **Web backend** uses the Parallel SDK when `PARALLEL_API_KEY` is set, otherwise the free Parallel MCP server.

**Setup guides:**
- [Slack](docs/SLACK_CONNECT.md)
- [Google Drive](docs/GDRIVE_CONNECT.md)
- [MCP Servers](docs/MCP_CONNECT.md)
- [Git-backed wiki](docs/WIKI_GIT.md)

## Evals

```sh
python -m evals wiring             # code-level invariants (no LLM)
python -m evals                    # behavioral cases, in-process
python -m evals --case <id>        # single case
python -m evals judges             # LLM-scored quality tier
```

See [`docs/EVALS.md`](docs/EVALS.md) for the full picture.

## Deploy to Railway

Scout runs on any cloud provider — we ship Railway scripts for one-command provisioning.

**Prereqs:** [Railway CLI](https://docs.railway.app/guides/cli) installed and `railway login` run.

### 1. Set up your production env

```sh
cp .env .env.production
```

Edit `.env.production` if any values should differ from local (e.g. a different Slack workspace, larger model budget, production-only credentials). The Railway scripts read `.env.production` first and fall back to `.env`.

> `.env.production` is gitignored. Don't commit it.

### 2. Provision and deploy

```sh
./scripts/railway/up.sh        # first-time: Postgres + app service
./scripts/railway/env.sh       # sync .env.production → Railway
./scripts/railway/redeploy.sh  # push code updates after up.sh
```

### 3. Your first deploy will fail — that's expected

Production endpoints require RBAC authorization (Scout enables it whenever `RUNTIME_ENV=prd`, which is the default). Without a `JWT_VERIFICATION_KEY`, the app refuses to serve traffic — Scout's job is to keep your company data off the public web. The fix is to generate a key from AgentOS and set it in your env.

### 4. Get your verification key

1. Open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=scout&utm_term=agentos), click **Add OS** → **Live**, and enter your Railway domain. The connection will fail — that's the app rejecting unsigned requests. Continue anyway.
2. Open **Settings**, generate an RSA key pair.
3. Paste the public key into `.env.production` (the full PEM block, no surrounding quotes):

```sh
JWT_VERIFICATION_KEY=-----BEGIN PUBLIC KEY-----
MIIBIjANBgkq...
-----END PUBLIC KEY-----
```

4. Sync and redeploy:

```sh
./scripts/railway/env.sh
./scripts/railway/redeploy.sh
```

Once redeployed, AgentOS connects, Scout starts serving requests, and every API call (UI, Slack, scheduled tasks) runs signed-and-verified from here on. The Agno control plane handles JWT issuance, session management, traces, metrics, and the web UI; Scout just verifies the JWTs it sees. See the [AgentOS Security docs](https://docs.agno.com/agent-os/security/overview) for details.

### 5. Point Slack at the new URL

1. Copy your Railway domain.
2. In your [Slack App settings](https://api.slack.com/apps) → **Event Subscriptions**, set the Request URL to `https://<your-railway-domain>/slack/events`.
3. Wait for Slack to verify.

If you were running ngrok locally, you can shut it down — Slack will route to the deployed instance.

### Opting out (not recommended)

If you must run production without auth — e.g. inside a private VPC behind another auth layer — flip `authorization=False` at [app/main.py:67](app/main.py:67) and redeploy. We strongly recommend keeping authorization on for any deploy that holds real company data; without it, anyone who guesses your Railway domain can query your CRM, wiki, and connected sources.

## What's next

- **Scheduled tasks** — Scout surfaces pending follow-ups automatically (e.g. a daily 8am summary of `scout_followups` where `due_at <= NOW()`).
- **Proactive provider actions** — `update_slack`, `update_github` running on cron, not just on demand.
- **GitHub, Gmail, Calendar providers** — built and verified on `feat/slack-interface`; landing in the next release once we've tested with real tokens.

## Architecture

Built on [Agno](https://github.com/agno-agi/agno) and AgentOS ([docs.agno.com](https://docs.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=scout&utm_term=docs)).

Implementation notes: [AGENTS.md](AGENTS.md).
