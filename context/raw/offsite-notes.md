# Engineering Offsite — Scout Adoption Plan

**Date:** 2026-04-11 (Thursday)
**Location:** Pier 48 meeting room, 9:30 AM – 4:00 PM
**Scribe:** Priya Ramanathan

## Attendees

- Maya Chen — VP Engineering (facilitator)
- Diego Alvarez — Platform lead
- Priya Ramanathan — Staff engineer, Developer Productivity
- Kenji Tanaka — Data infra lead
- Sarah O'Connell — Engineering manager, API team
- Reza Haddad — Senior engineer, Growth
- Nadia Park — Security engineer

## Context

We've been running Scout on the platform team for three weeks as a pilot. Maya wants to decide today whether to roll it out to all of engineering, and if so, on what timeline and with what guardrails. The pilot has been useful — Diego's team reports that onboarding questions that used to ping Slack now get answered by Scout against the compiled wiki. But it's been bumpy in a few places. This offsite is where we reconcile.

## What Scout actually is

Maya opened by asking everyone to describe Scout in one sentence, to check we're aligned before we make decisions.

Rough consensus:

> Scout is a context agent. You drop your team's documents into `context/raw/` and Scout compiles them into a wiki that a team of specialists — Navigator, Compiler, Researcher — can navigate to answer questions.

Reza pushed back: "It's not a chatbot, it's a teammate that *navigates* context graphs instead of retrieving chunks." Agreed this framing matters for how we pitch it to the rest of engineering.

## Decisions

### D1 — Roll out Scout to all engineering teams by end of Q2

Approved unanimously. Timeline: first new team (API) onboarded by 2026-04-25, remaining teams in weekly cohorts through 2026-06-06. No team joins without a point person who has done the Scout walkthrough.

### D2 — The wiki is the boundary, not the raw files

Every team will follow the same rule: raw documents go into `context/raw/`, the Compiler produces clean articles into `context/compiled/articles/`, and Navigator only reads the compiled wiki. No one in the team should be hand-editing files in `context/compiled/` — if a wiki article is wrong, fix the raw source and let the compiler regenerate.

Exception: if Compiler output is materially wrong in a way the raw source doesn't explain, edit the compiled article directly. Scout's user-edit protection will flag it and stop overwriting on the next compile pass.

### D3 — One Scout instance per workspace

We considered running a separate Scout per team. Rejected — the whole point of Scout is that it navigates across sources. A per-team split fragments the graph. We'll run one instance, scoped by `SCOUT_WORKSPACE_ID` later when multi-workspace lands.

### D4 — Sources to wire up, in order

1. **GitHub** — the repos we actively work in: `acme/api`, `acme/web`, `acme/infra`. Diego will wire read-only GitHub access for CodeExplorer (`GITHUB_ACCESS_TOKEN` in the scout service env). CodeExplorer clones on demand — no pre-configured repo list. Target: 2026-04-18.
2. **Drive** — the `Engineering` shared drive. Only folders, not the whole org. Sarah will collect the folder IDs for `Engineering/Handbook`, `Engineering/RFCs`, and `Engineering/Postmortems`. Target: 2026-04-22.
3. **Slack** — `#eng`, `#eng-platform`, `#eng-api`, `#eng-incidents`. Slack is live-read, so threads stay where they are; Scout just queries them. Nadia will review the scope before we install. Target: 2026-05-02.
4. **S3** — the `acme-eng-archive` bucket that holds old PDFs (architecture diagrams, vendor contracts, post-mortem decks). Compile-only; let Scout turn them into wiki articles. Kenji will handle. Target: 2026-05-09.

No Notion for now. We'll reassess in July.

### D5 — Wiki voice is the existing voice guide, unchanged

We read `context/voice/wiki-article.md` aloud as a group. Consensus: it's tight and correct. "Short, dense, encyclopedic. No throat-clearing." Reza wanted to add a section on code-block formatting for how-to articles; Priya pointed out the voice guide already handles that implicitly. Leaving it alone.

### D6 — `#scout-updates` is the only place Scout posts to

Maya was firm on this. The moment Scout starts pinging random channels, people will mute it. All scheduled tasks (daily briefings, inbox digests, weekly reviews) post to `#scout-updates` only. Individual engineers can @-mention Scout in any channel Scout is installed in, but Scout never initiates posts outside `#scout-updates`.

### D7 — Compile runs every hour, not every ten minutes

Diego argued the 10-minute cadence was too aggressive — it churns the LLM spend and compiled articles aren't that time-sensitive. Moved to every hour on the hour. Users can still run `docker exec -it scout-api python -m scout compile` manually if they need an immediate recompile.

### D8 — Gmail is draft-only, forever

Nadia raised the obvious concern: an agent with send authority is a phishing vector. We confirmed Scout's Gmail surface already excludes send at the code level. Not revisiting.

### D9 — Calendar is read-only for now

Same rationale as D8. We'll reconsider write access (create_event, update_event) once we have a clear case and guardrails. Until then, read-only.

### D10 — Evals run in CI on every PR that touches `scout/`

Priya will wire this up. The static eval suite (`python -m evals`) takes under 90 seconds. Live evals (`python -m evals.live`) need a running container and are gated on a label. Target: 2026-04-30.

## Rejected or deferred

- **Auto-ingest from Slack**: Reza pitched having Scout auto-ingest `#eng-rfc` threads into `context/raw/`. Rejected — too easy for noise to pollute the wiki. Engineers can manually ask Scout to ingest a specific URL or thread.
- **Private wiki article permissions**: asked whether Scout should honor per-document ACLs from the source. Deferred. For now, if a source is in Scout, anyone who can talk to Scout can read it. We'll revisit when multi-workspace lands.
- **Fine-tuned model**: Kenji floated fine-tuning a smaller model on the wiki. Deferred. Current gpt-5.4 performance is fine; we'll reconsider when spend becomes a real issue.

## Action items

| # | Owner | Item | Due |
|---|-------|------|-----|
| A1 | Diego | Wire `GITHUB_ACCESS_TOKEN` (read-only PAT) so CodeExplorer can reach `acme/api`, `acme/web`, `acme/infra` | 2026-04-18 |
| A2 | Sarah | Collect Drive folder IDs for Handbook, RFCs, Postmortems | 2026-04-22 |
| A3 | Nadia | Security review of Slack install scope + post-install audit | 2026-05-02 |
| A4 | Kenji | Point S3 compile at `acme-eng-archive` bucket | 2026-05-09 |
| A5 | Priya | Add eval CI pipeline on PRs touching `scout/` | 2026-04-30 |
| A6 | Priya | Write the Scout walkthrough doc every new team runs through | 2026-04-25 |
| A7 | Maya | Announce the rollout + `#scout-updates` channel convention at all-hands | 2026-04-18 |
| A8 | Reza | Prepare the onboarding-team adoption report for the 2026-04-25 follow-up | 2026-04-24 |

## Follow-up

Same group, same room, 2026-04-25 at 10:00 AM. Goal: review D1 progress against A1–A7, sign off on API team going live.
