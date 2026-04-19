---
source: local:raw:offsite-notes.md
source_url: file:///app/context/raw/offsite-notes.md
source_hash: 0d6f0ac648d447521aed82aac666fa950b9ff24dc4737a90fd8007c85c9b017f
compiled_at: 2026-04-18T18:35:08Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags: [scout, rollout, engineering, onboarding]
backlinks: [[[scout-wiki]], [[scout-sources]], [[scout-operations]], [[scout-security]]]
---

# Scout Adoption Plan

Engineering approves rolling out Scout to all teams by end of Q2 2026, using one shared instance and a compiled wiki as the system boundary. The plan also sets source priorities, posting rules, compile cadence, and security constraints.

## Overview

The offsite took place on 2026-04-11 (Thursday) at Pier 48 meeting room, 9:30 AM – 4:00 PM. Priya Ramanathan was scribe.

Attendees:
- Maya Chen — VP Engineering (facilitator)
- Diego Alvarez — Platform lead
- Priya Ramanathan — Staff engineer, Developer Productivity
- Kenji Tanaka — Data infra lead
- Sarah O'Connell — Engineering manager, API team
- Reza Haddad — Senior engineer, Growth
- Nadia Park — Security engineer

## Context

Scout has run on the platform team for three weeks as a pilot. The pilot reduced onboarding questions in Slack by answering against the compiled wiki, but had enough rough edges that leadership used the offsite to decide whether to expand it and under what guardrails.

## Definition

The group aligned on this definition:

> Scout is a context agent. You drop your team's documents into `context/raw/` and Scout compiles them into a wiki that a team of specialists — Navigator, Compiler, Researcher — can navigate to answer questions.

A refinement also carried forward: Scout is not a chatbot. It is a teammate that navigates context graphs instead of retrieving chunks. That framing matters for internal rollout.

## Decisions

### D1 — Rollout timeline

Scout rolls out to all engineering teams by end of Q2.

- First new team: API by 2026-04-25
- Remaining teams: weekly cohorts through 2026-06-06
- Requirement: no team joins without a point person who has completed the Scout walkthrough

### D2 — Compiled wiki boundary

The wiki, not the raw files, is the system boundary.

Standard flow:
- Raw documents go in `context/raw/`
- Compiler writes articles to `context/compiled/articles/`
- Navigator reads only the compiled wiki

Rule:
- Team members should not hand-edit files in `context/compiled/`
- If an article is wrong, fix the raw source and recompile

Exception:
- If Compiler output is materially wrong in a way the raw source does not explain, edit the compiled article directly
- Scout's user-edit protection flags that article and stops overwriting it on the next compile pass

### D3 — Instance model

Engineering uses one Scout instance per workspace, not one per team.

Rejected option:
- Separate Scout instances per team

Reason:
- Per-team instances fragment the graph
- Scout's value is cross-source navigation

Future plan:
- Scope by `SCOUT_WORKSPACE_ID` when multi-workspace lands

### D4 — Source rollout order

Sources will be wired in this order:

1. **GitHub**
   - Repos: `acme/api`, `acme/web`, `acme/infra`
   - Diego wires read-only GitHub access for CodeExplorer
   - Env var: `GITHUB_ACCESS_TOKEN` in the scout service env
   - CodeExplorer clones on demand; no pre-configured repo list
   - Target: 2026-04-18

2. **Drive**
   - Scope: `Engineering` shared drive
   - Limit: folders only, not the whole org
   - Sarah collects folder IDs for:
     - `Engineering/Handbook`
     - `Engineering/RFCs`
     - `Engineering/Postmortems`
   - Target: 2026-04-22

3. **Slack**
   - Channels: `#eng`, `#eng-platform`, `#eng-api`, `#eng-incidents`
   - Slack is live-read; Scout queries threads in place rather than ingesting them
   - Nadia reviews scope before install
   - Target: 2026-05-02

4. **S3**
   - Bucket: `acme-eng-archive`
   - Contents mentioned: old PDFs such as architecture diagrams, vendor contracts, and post-mortem decks
   - Mode: compile-only into wiki articles
   - Kenji handles setup
   - Target: 2026-05-09

Deferred:
- No Notion for now
- Reassess in July

### D5 — Wiki voice guide

The team keeps `context/voice/wiki-article.md` unchanged.

Consensus:
- The guide is already correct
- Desired style: short, dense, encyclopedic, with no throat-clearing

Considered change:
- Reza proposed adding code-block formatting guidance for how-to articles
- Priya noted the current guide already handles that implicitly

Outcome:
- No change

### D6 — Posting channel

`#scout-updates` is the only channel Scout may post to on its own.

Rules:
- All scheduled tasks post only to `#scout-updates`
- This includes daily briefings, inbox digests, and weekly reviews
- Engineers may @-mention Scout in any installed channel
- Scout never initiates posts outside `#scout-updates`

### D7 — Compile cadence

Compile runs every hour, not every ten minutes.

Reason:
- A 10-minute cadence drives unnecessary LLM spend
- Compiled articles are not time-sensitive enough to justify it

Manual override:
- Users can run `docker exec -it scout-api python -m scout compile` for an immediate recompile

### D8 — Gmail authority

Gmail remains draft-only, permanently.

Reason:
- Send authority creates a phishing vector

Note:
- Scout's Gmail integration already excludes send at the code level
- The team does not plan to revisit this

### D9 — Calendar authority

Calendar is read-only for now.

Reason:
- Same risk rationale as Gmail

Deferred capability:
- `create_event`
- `update_event`

Condition for reconsideration:
- A clear use case and explicit guardrails

### D10 — Evals in CI

Evals run in CI on every PR that touches `scout/`.

Details:
- Priya will wire this up
- Static eval suite: `python -m evals`
- Runtime: under 90 seconds
- Live evals: `python -m evals.live`
- Live evals require a running container and are gated on a label
- Target: 2026-04-30

## Rejected or deferred

- **Auto-ingest from Slack**
  - Proposal: auto-ingest `#eng-rfc` threads into `context/raw/`
  - Owner of proposal: Reza
  - Decision: rejected
  - Reason: too much noise risk in the wiki
  - Allowed alternative: engineers can manually ask Scout to ingest a specific URL or thread

- **Private wiki article permissions**
  - Question: whether Scout should honor per-document ACLs from the source
  - Decision: deferred
  - Current rule: if a source is in Scout, anyone who can talk to Scout can read it
  - Revisit when multi-workspace lands

- **Fine-tuned model**
  - Proposal owner: Kenji
  - Proposal: fine-tune a smaller model on the wiki
  - Decision: deferred
  - Reason: current `gpt-5.4` performance is acceptable
  - Revisit when model spend becomes a real issue

## Action items

| # | Owner | Item | Due |
|---|---|---|---|
| A1 | Diego | Wire `GITHUB_ACCESS_TOKEN` (read-only PAT) so CodeExplorer can reach `acme/api`, `acme/web`, `acme/infra` | 2026-04-18 |
| A2 | Sarah | Collect Drive folder IDs for Handbook, RFCs, Postmortems | 2026-04-22 |
| A3 | Nadia | Security review of Slack install scope + post-install audit | 2026-05-02 |
| A4 | Kenji | Point S3 compile at `acme-eng-archive` bucket | 2026-05-09 |
| A5 | Priya | Add eval CI pipeline on PRs touching `scout/` | 2026-04-30 |
| A6 | Priya | Write the Scout walkthrough doc every new team runs through | 2026-04-25 |
| A7 | Maya | Announce the rollout + `#scout-updates` channel convention at all-hands | 2026-04-18 |
| A8 | Reza | Prepare the onboarding-team adoption report for the 2026-04-25 follow-up | 2026-04-24 |

## Follow-up

The follow-up is scheduled for 2026-04-25 at 10:00 AM, with the same group in the same room.

Goal:
- Review D1 progress against A1–A7
- Sign off on the API team going live

## See also

- [[scout-wiki]]
- [[scout-sources]]
- [[scout-operations]]
- [[scout-security]]
