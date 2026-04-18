---
source: local:raw:offsite-notes.md
source_url: file:///app/context/raw/offsite-notes.md
source_hash: 0c1e7904259d88d7b8d82d74ca5c04b644c5df07e80d6347d21b8efd01e1e37a
compiled_at: 2026-04-18T12:37:07Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags: [scout, onboarding, engineering, rollout]
backlinks: [[[scout]], [[wiki-article-voice-guide]], [[scout-evals]], [[scout-slack-integration]]]
---

# Scout Adoption Plan

Engineering approves rolling out [[Scout]] to all engineering teams by end of Q2, with API onboarding first by 2026-04-25 and remaining teams joining in weekly cohorts through 2026-06-06. The rollout keeps a single shared Scout instance, treats the compiled wiki as the retrieval boundary, and applies conservative guardrails around Slack, Gmail, Calendar, and source ingestion.

## Offsite details

- **Date:** 2026-04-11 (Thursday)
- **Location:** Pier 48 meeting room, 9:30 AM – 4:00 PM
- **Scribe:** Priya Ramanathan
- **Facilitator:** Maya Chen

## Attendees

- Maya Chen — VP Engineering
- Diego Alvarez — Platform lead
- Priya Ramanathan — Staff engineer, Developer Productivity
- Kenji Tanaka — Data infra lead
- Sarah O'Connell — Engineering manager, API team
- Reza Haddad — Senior engineer, Growth
- Nadia Park — Security engineer

## Context

Scout had run on the platform team for three weeks as a pilot before this decision. The pilot reduced onboarding questions in Slack by answering against the compiled wiki, but the team wanted alignment on rollout timing and guardrails.

## Scout definition

Group consensus defined Scout as a context agent: teams place documents in `context/raw/`, Scout compiles them into a wiki, and specialists such as Navigator, Compiler, and Researcher use that wiki to answer questions.

Reza Haddad objected to framing Scout as a chatbot. The group agreed the better framing is that Scout is a teammate that navigates context graphs instead of retrieving chunks, and that this distinction matters for internal positioning.

## Decisions

### D1 — Engineering-wide rollout

Scout rolls out to all engineering teams by end of Q2.

- First new team: API, by 2026-04-25
- Remaining teams: weekly cohorts through 2026-06-06
- Requirement: no team joins without a point person who has completed the Scout walkthrough

### D2 — Compiled wiki boundary

The compiled wiki is the operational boundary, not the raw files.

- Raw documents go in `context/raw/`
- Compiler writes articles to `context/compiled/articles/`
- Navigator reads only the compiled wiki
- Team members should not hand-edit files in `context/compiled/`
- If a wiki article is wrong, fix the raw source and recompile

Exception:

- If Compiler output is materially wrong in a way the raw source does not explain, edit the compiled article directly
- Scout's user-edit protection will flag the change and stop overwriting it on the next compile pass

### D3 — Single Scout instance

Engineering will run one Scout instance per workspace, not one per team.

A separate instance per team was rejected because it fragments the context graph. Future scoping will use `SCOUT_WORKSPACE_ID` when multi-workspace support lands.

### D4 — Source onboarding order

Sources will be added in this order:

1. **GitHub**
   - Repos: `acme/api`, `acme/web`, `acme/infra`
   - Owner: Diego Alvarez
   - Work: set `GITHUB_REPOS` and a read-only PAT
   - Target: 2026-04-18

2. **Drive**
   - Scope: `Engineering` shared drive, folders only
   - Folders: `Engineering/Handbook`, `Engineering/RFCs`, `Engineering/Postmortems`
   - Owner: Sarah O'Connell
   - Work: collect folder IDs
   - Target: 2026-04-22

3. **Slack**
   - Channels: `#eng`, `#eng-platform`, `#eng-api`, `#eng-incidents`
   - Behavior: live-read only; threads remain in Slack and Scout queries them there
   - Owner: Nadia Park
   - Work: review installation scope
   - Target: 2026-05-02

4. **S3**
   - Bucket: `acme-eng-archive`
   - Contents include old PDFs such as architecture diagrams, vendor contracts, and post-mortem decks
   - Behavior: compile-only into wiki articles
   - Owner: Kenji Tanaka
   - Target: 2026-05-09

Notion is excluded for now and will be reassessed in July.

### D5 — Wiki voice guide

The team keeps `context/voice/wiki-article.md` unchanged as the wiki voice guide.

The group explicitly endorsed the current style: short, dense, encyclopedic, and without throat-clearing. Reza Haddad proposed adding code-block formatting guidance for how-to articles, but Priya Ramanathan noted the guide already handles that implicitly, so no change was made.

### D6 — Posting channel policy

`#scout-updates` is the only channel where Scout may initiate posts.

- Scheduled tasks such as daily briefings, inbox digests, and weekly reviews post only to `#scout-updates`
- Engineers may still @-mention Scout in any channel where it is installed
- Scout must not initiate posts outside `#scout-updates`

### D7 — Compile cadence

Compile runs move from every ten minutes to every hour on the hour.

Reason given: the 10-minute cadence created unnecessary LLM spend and article freshness did not justify it. Manual recompiles remain available with:

```bash
docker exec -it scout-api python -m scout compile
```

### D8 — Gmail permissions

Gmail remains draft-only, permanently.

The decision is based on security: agent send authority is a phishing vector. The group confirmed Scout already excludes Gmail send at the code level and will not revisit this.

### D9 — Calendar permissions

Calendar remains read-only for now.

Write access such as `create_event` and `update_event` is deferred until there is a clear use case and explicit guardrails.

### D10 — Evals in CI

Evals will run in CI on every PR that touches `scout/`.

- Owner: Priya Ramanathan
- Static eval suite: `python -m evals`
- Runtime: under 90 seconds
- Live evals: `python -m evals.live`
- Requirement for live evals: running container
- Gating: label-based
- Target: 2026-04-30

## Rejected or deferred

- **Auto-ingest from Slack**
  - Proposal: auto-ingest `#eng-rfc` threads into `context/raw/`
  - Proposed by: Reza Haddad
  - Decision: rejected
  - Reason: too much risk of wiki pollution from noise
  - Allowed alternative: engineers may manually ask Scout to ingest a specific URL or thread

- **Private wiki article permissions**
  - Question: whether Scout should honor per-document ACLs from the source
  - Decision: deferred
  - Current rule: if a source is in Scout, anyone who can talk to Scout can read it
  - Revisit point: when multi-workspace lands

- **Fine-tuned model**
  - Proposal: fine-tune a smaller model on the wiki
  - Proposed by: Kenji Tanaka
  - Decision: deferred
  - Reason: current `gpt-5.4` performance is sufficient
  - Revisit point: when model spend becomes a real issue

## Action items

| # | Owner | Item | Due |
|---|---|---|---|
| A1 | Diego | Wire `GITHUB_REPOS=acme/api,acme/web,acme/infra` and read-only PAT | 2026-04-18 |
| A2 | Sarah | Collect Drive folder IDs for Handbook, RFCs, Postmortems | 2026-04-22 |
| A3 | Nadia | Security review of Slack install scope + post-install audit | 2026-05-02 |
| A4 | Kenji | Point S3 compile at `acme-eng-archive` bucket | 2026-05-09 |
| A5 | Priya | Add eval CI pipeline on PRs touching `scout/` | 2026-04-30 |
| A6 | Priya | Write the Scout walkthrough doc every new team runs through | 2026-04-25 |
| A7 | Maya | Announce the rollout + `#scout-updates` channel convention at all-hands | 2026-04-18 |
| A8 | Reza | Prepare the onboarding-team adoption report for the 2026-04-25 follow-up | 2026-04-24 |

## Follow-up

The next review is scheduled for 2026-04-25 at 10:00 AM in the same room with the same group. The goal is to review D1 progress against A1–A7 and sign off on the API team going live.

## See also

- [[Scout]]
- [[wiki-article-voice-guide]]
- [[scout-evals]]
- [[scout-slack-integration]]
