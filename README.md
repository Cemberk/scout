# Scout

Scout is an enterprise context agent. It ingests, organizes, and serves your company's knowledge base.

Feed it your docs. Policies, runbooks, architecture docs, meeting notes, reports. Scout organizes everything into two layers: a compiled wiki for knowledge depth (concepts, summaries, cross-references) and SQL tables for structured data (contacts, projects, decisions, teams). A learning loop compounds every interaction.

Ask Scout a question, it navigates across sources to find the answer. Not semantic search over chunks. SQL for structured queries. The wiki index for knowledge routing. File structure for document retrieval. Each source queried on its own terms.

## Quick Start

```sh
git clone https://github.com/agno-agi/scout.git && cd scout
cp example.env .env  # Add OPENAI_API_KEY
docker compose up -d --build
docker compose exec scout-api python context/load_context.py
```

Open [localhost:8000](http://localhost:8000) to chat with Scout.

## How It Works

Scout is a team of five specialist agents coordinated by a leader:

```
Scout (Leader)
├── Navigator    — the workhorse: SQL, files, documents, wiki, email, calendar, web search
├── Researcher   — gathers sources from the web, saves to raw/ with frontmatter
├── Compiler     — reads raw sources, compiles structured wiki articles
├── Linter       — runs health checks on the wiki, finds gaps and contradictions
└── Syncer       — commits and pushes context/ to GitHub for durability
```

**Navigator** handles everything users ask. SQL queries for structured data, file reads for documents, wiki lookups for compiled knowledge, web search for live information. It has full agentic memory — learns from every interaction.

**Researcher** gathers source material from the web using Parallel (search + extract) and saves it to `raw/` with YAML frontmatter. Conditional on `PARALLEL_API_KEY`.

**Compiler** reads uncompiled raw documents and produces wiki articles — concept pages, source summaries, and a master index. Incremental: only processes new files, never rewrites the whole wiki.

**Linter** runs periodic health checks. Finds contradictions, stale articles, missing concepts, orphaned pages, thin articles, and duplicate coverage. Writes a lint report with suggested actions.

**Syncer** commits and pushes `context/` to GitHub after file-creating workflows. Conditional on `GITHUB_ACCESS_TOKEN` + `SCOUT_REPO_URL`.

## Knowledge Base Pipeline

```
Ingest → raw/ (with frontmatter) → Compile → wiki/ (concepts + summaries + index) → Query → Learn
```

```
context/
├── about-us.md              # Company background
├── preferences.md           # Response style, conventions
├── voice/                   # Tone guides (email, slack, document)
├── templates/               # Document scaffolds
├── meetings/                # Saved meeting notes
├── projects/                # Project briefs
├── raw/                     # Ingested source material
│   └── .manifest.json       # Tracks ingest/compile state
└── wiki/                    # Compiled knowledge base
    ├── index.md             # Master index (~5K tokens, fits in one read)
    ├── concepts/            # One article per concept
    ├── summaries/           # One summary per raw document
    └── outputs/             # Filed query results
```

## Structured Data

Scout owns SQL tables for structured data. Tables are created on demand from natural conversation:

- "Save a note: met with Sarah from Acme, she's interested in a partnership" → `scout_notes` row, tagged `['sarah', 'acme', 'partnership']`
- "Who owns the billing service?" → SQL query across `scout_teams` and `scout_projects`

Schema conventions: `scout_` prefix, `user_id` scoping on every query, `TEXT[]` tags as the cross-table connector.

## The Learning Loop

Two knowledge systems power Scout's improvement:

| System | Purpose | Prefixes |
|--------|---------|----------|
| **Knowledge** (the map) | Metadata routing — where things live | `File:`, `Schema:`, `Source:`, `Discovery:` |
| **Learnings** (the compass) | Operational memory — what works | `Retrieval:`, `Pattern:`, `Correction:` |

Knowledge tells Scout where to look. Learnings tell it how to look. Corrections always win.

## Execution Loop

Every interaction follows five steps:

1. **Classify** — determine intent (capture, retrieve, connect, research, draft, etc.)
2. **Recall** — search knowledge, learnings, wiki index, SQL tables, documents
3. **Read** — pull from identified sources, summarize per source
4. **Act** — execute tool calls, governance rules apply
5. **Learn** — save discoveries, retrieval strategies, patterns

**Example:** "What's our deployment process?"
1. Classify: `document_search`
2. Recall: search knowledge for `Discovery:` entries about deployment
3. Read: navigate `documents/engineering-docs/runbooks/deployment.md`
4. Act: return blue-green deployment process with source citation
5. Learn: save `Discovery: deployment` → `engineering-docs/runbooks/deployment.md`

## Integrations

<details>
<summary>Gmail + Google Calendar</summary>

Requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_PROJECT_ID`. All three must be set.

- Email: search, read, draft (sending disabled at code level)
- Calendar: view, create, update events (external attendees require confirmation)

</details>

<details>
<summary>Slack</summary>

Requires `SLACK_TOKEN` and `SLACK_SIGNING_SECRET`.

- Leader posts to Slack channels (scheduled tasks, user requests)
- Thread-based sessions for continuity

</details>

<details>
<summary>Parallel (Enhanced Research)</summary>

Requires `PARALLEL_API_KEY`. Enables the Researcher agent.

- `parallel_search` for web search
- `parallel_extract` for full content extraction
- Auto-ingest URLs with content

</details>

<details>
<summary>Exa (Web Search)</summary>

Set `EXA_API_KEY` for web search via Navigator and Linter. Works without Parallel for basic searches.

</details>

<details>
<summary>Git Sync</summary>

Requires `GITHUB_ACCESS_TOKEN` and `SCOUT_REPO_URL`.

- Syncer commits and pushes after file-creating workflows
- Pull on startup + every 30 minutes
- No volumes needed — git is the persistence layer

</details>

## Scheduled Tasks

All times US/Eastern.

| Task | Schedule | Description |
|------|----------|-------------|
| Context Refresh | Daily 8 AM | Re-index context files into knowledge |
| Daily Briefing | Weekdays 8 AM | Calendar, emails, priorities |
| Wiki Compile | Daily 9 AM | Process new raw sources into articles |
| Inbox Digest | Weekdays 12 PM | Midday email digest |
| Learning Summary | Monday 10 AM | Weekly learning system summary |
| Weekly Review | Friday 5 PM | End-of-week review draft |
| Wiki Lint | Sunday 8 AM | Wiki health check |
| Sync Pull | Every 30 min | Pull remote context/ from GitHub |

## Sample Documents

Scout ships with sample enterprise documents from Acme Corp for immediate exploration:

| Directory | Contents |
|-----------|----------|
| `company-docs/policies/` | Employee handbook, security policy, data retention |
| `company-docs/hr/` | Benefits guide, onboarding checklist |
| `company-docs/planning/` | Q4 2024 OKRs, 2024 strategy |
| `engineering-docs/runbooks/` | Deployment, incident response, on-call guide |
| `engineering-docs/architecture/` | System overview, API design |
| `data-exports/reports/` | Q4 2024 metrics |

## Example Prompts

```
# Retrieve
What's our PTO policy?
How do I deploy to production?
What's the SLA for SEV1 incidents?

# Capture
Save a note: Met with the security team about the Q4 audit
Add Sarah Chen to contacts — she's the VP of Engineering at Acme

# Connect
Prep me for my meeting with the infrastructure team — what do I need to know?

# Ingest
Ingest this article: https://example.com/article-on-context-agents

# Compile
Compile any new sources into the wiki

# Lint
Run a health check on the wiki

# Draft
Draft a Slack message about the API migration status
Draft an email to the engineering leads about the architecture review
```

## Deploy to Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/scout)

```sh
railway up
railway run python context/load_context.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `EXA_API_KEY` | No | Web search for Navigator + Linter |
| `PARALLEL_API_KEY` | No | Enables Researcher agent |
| `GOOGLE_CLIENT_ID` | No | Gmail + Calendar (all 3 required) |
| `GOOGLE_CLIENT_SECRET` | No | Gmail + Calendar |
| `GOOGLE_PROJECT_ID` | No | Gmail + Calendar |
| `SLACK_TOKEN` | No | Slack bot token |
| `SLACK_SIGNING_SECRET` | No | Slack event verification |
| `GITHUB_ACCESS_TOKEN` | No | Git sync (both required) |
| `SCOUT_REPO_URL` | No | Git sync repo URL |
| `SCOUT_CONTEXT_DIR` | No | Context directory (default: `./context`) |
| `DOCUMENTS_DIR` | No | Documents directory (default: `./documents`) |
| `DB_HOST` | No | Database host (default: localhost) |
| `DB_PORT` | No | Database port (default: 5432) |
| `DB_USER` | No | Database user (default: ai) |
| `DB_PASS` | No | Database password (default: ai) |
| `DB_DATABASE` | No | Database name (default: ai) |
| `RUNTIME_ENV` | No | `dev` for hot reload, `prd` for RBAC |
