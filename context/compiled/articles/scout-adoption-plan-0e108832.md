---
source: local:raw:offsite-notes.md
source_url: file:///app/context/raw/offsite-notes.md
source_hash: 0d6f0ac648d447521aed82aac666fa950b9ff24dc4737a90fd8007c85c9b017f
compiled_at: 2026-04-19T11:05:54Z
compiled_by: scout-compiler
user_edited: false
needs_split: true
tags: [scout, rollout, engineering, onboarding, policy]
backlinks: [[[scout-wiki-boundary]], [[scout-source-integrations]], [[scout-operations-guardrails]], [[scout-follow-up]]]
---

# Scout Adoption Plan

Engineering approved a full Scout rollout by the end of Q2, with API onboarding by 2026-04-25 and remaining teams joining in weekly cohorts through 2026-06-06. The plan keeps one shared Scout instance, treats the compiled wiki as the serving boundary, and adds conservative guardrails around posting, email, calendar, and source ingestion.

## Offsite details

- Date: 2026-04-11 (Thursday)
- Location: Pier 48 meeting room, 9:30 AM – 4:00 PM
- Scribe: Priya Ramanathan

## Attendees

- Maya Chen — VP Engineering (facilitator)
- Diego Alvarez — Platform lead
- Priya Ramanathan — Staff engineer, Developer Productivity
- Kenji Tanaka — Data infra lead
- Sarah O'Connell — Engineering manager, API team
- Reza Haddad — Senior engineer, Growth
- Nadia Park — Security engineer

## Context

Scout had run on the platform team for three weeks as a pilot. The pilot reduced Slack onboarding questions by answering against the compiled wiki, but the group met to decide whether to expand to all of engineering and under what guardrails.

## Definition

The group aligned on this definition:

> Scout is a context agent. You drop your team's documents into `context/raw/` and Scout compiles them into a wiki that a team of specialists — Navigator, Compiler, Researcher — can navigate to answer questions.

A framing note also landed: Scout is not a chatbot; it is a teammate that navigates context graphs instead of retrieving chunks.

## Decisions

### D1 — Full rollout by end of Q2

Approved unanimously.

- First new team: API by 2026-04-25
- Remaining teams: weekly cohorts through 2026-06-06
- Requirement: no team joins without a point person who has completed the Scout walkthrough

### D2 — Compiled wiki is the boundary

All teams use the same flow:

- Put raw documents in `context/raw/`
- Let Compiler generate articles in `context/compiled/articles/`
- Let Navigator read only the compiled wiki

Rules:

- Teams should not hand-edit files in `context/compiled/`
- If a wiki article is wrong, fix the raw source and recompile

Exception:

- If Compiler output is materially wrong and the raw source does not explain the error, edit the compiled article directly
- Scout's user-edit protection will flag the file and stop overwriting it on the next compile pass

### D3 — One Scout instance per workspace

The team rejected separate Scout instances per team because that would fragment the context graph. Engineering will run one instance and later scope by `SCOUT_WORKSPACE_ID` when multi-workspace support lands.

### D4 — Source rollout order

1. **GitHub**
   - Repos: `acme/api`, `acme/web`, `acme/infra`
   - Owner: Diego
   - Requirement: read-only GitHub access for CodeExplorer via `GITHUB_ACCESS_TOKEN` in the scout service env
   - Behavior: CodeExplorer clones on demand; no pre-configured repo list
   - Target: 2026-04-18

2. **Drive**
   - Scope: `Engineering` shared drive, folders only
   - Folders: `Engineering/Handbook`, `Engineering/RFCs`, `Engineering/Postmortems`
   - Owner: Sarah
   - Target: 2026-04-22

3. **Slack**
   - Channels: `#eng`, `#eng-platform`, `#eng-api`, `#eng-incidents`
   - Behavior: live-read only; threads remain in Slack and Scout queries them directly
   - Owner: Nadia for scope review before install
   - Target: 2026-05-02

4. **S3**
   - Bucket: `acme-eng-archive`
   - Contents: old PDFs such as architecture diagrams, vendor contracts, and post-mortem decks
   - Mode: compile-only into wiki articles
   - Owner: Kenji
   - Target: 2026-05-09

Deferred source:

- No Notion for now
- Reassess in July

### D5 — Keep the existing wiki voice guide

The group reviewed `context/voice/wiki-article.md` and left it unchanged. Consensus phrasing was: short, dense, encyclopedic, with no throat-clearing.

Reza proposed adding code-block formatting guidance for how-to articles. Priya noted the existing guide already covers this implicitly. No change was made.

### D6 — Posting restricted to `#scout-updates`

Scout posts scheduled output only to `#scout-updates`.

This includes:

- daily briefings
- inbox digests
- weekly reviews

Engineers may still @-mention Scout in any channel where Scout is installed, but Scout does not initiate posts outside `#scout-updates`.

### D7 — Compile hourly

Compile cadence moved from every 10 minutes to every hour on the hour to reduce LLM spend. Manual recompiles remain available with:

```bash
docker exec -it scout-api python -m scout compile
```

### D8 — Gmail remains draft-only

Gmail send authority is excluded permanently. The team confirmed the code already prevents send access and does not plan to revisit that decision.

### D9 — Calendar remains read-only

Calendar access stays read-only for now. Write actions such as `create_event` and `update_event` are deferred until there is a clear use case and guardrails.

### D10 — Evals in CI for `scout/` PRs

Evals will run in CI on every PR that touches `scout/`.

- Owner: Priya
- Static evals: `python -m evals`, under 90 seconds
- Live evals: `python -m evals.live`
- Live eval requirement: a running container
- Live eval gating: label-based
- Target: 2026-04-30

## Rejected or deferred

- **Auto-ingest from Slack**
  - Proposal: auto-ingest `#eng-rfc` threads into `context/raw/`
  - Outcome: rejected
  - Reason: too much risk of noise polluting the wiki
  - Allowed alternative: engineers may manually ask Scout to ingest a specific URL or thread

- **Private wiki article permissions**
  - Question: should Scout honor per-document ACLs from source systems
  - Outcome: deferred
  - Current rule: if a source is in Scout, anyone who can talk to Scout can read it
  - Revisit when multi-workspace lands

- **Fine-tuned model**
  - Proposal: fine-tune a smaller model on the wiki
  - Outcome: deferred
  - Reason: current `gpt-5.4` performance is acceptable
  - Revisit when spend becomes a real issue

## Action items

- **A1 — Diego**
  - Wire `GITHUB_ACCESS_TOKEN` (read-only PAT) so CodeExplorer can reach `acme/api`, `acme/web`, `acme/infra`
  - Due: 2026-04-18

- **A2 — Sarah**
  - Collect Drive folder IDs for Handbook, RFCs, Postmortems
  - Due: 2026-04-22

- **A3 — Nadia**
  - Security review of Slack install scope plus post-install audit
  - Due: 2026-05-02

- **A4 — Kenji**
  - Point S3 compile at `acme-eng-archive` bucket
  - Due: 2026-05-09

- **A5 — Priya**
  - Add eval CI pipeline on PRs touching `scout/`
  - Due: 2026-04-30

- **A6 — Priya**
  - Write the Scout walkthrough document every new team runs through
  - Due: 2026-04-25

- **A7 — Maya**
  - Announce the rollout and `#scout-updates` convention at all-hands
  - Due: 2026-04-18

- **A8 — Reza**
  - Prepare the onboarding-team adoption report for the 2026-04-25 follow-up
  - Due: 2026-04-24

## Follow-up

- Date: 2026-04-25
- Time: 10:00 AM
- Location: same group, same room
- Goal: review D1 progress against A1–A7 and sign off on API team going live

## See also

- [[scout-wiki-boundary]]
- [[scout-source-integrations]]
- [[scout-operations-guardrails]]
- [[scout-follow-up]]
