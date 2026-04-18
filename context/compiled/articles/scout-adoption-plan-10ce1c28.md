---
source: local:raw:offsite-notes.md
source_url: file:///app/context/raw/offsite-notes.md
source_hash: 0c1e7904259d88d7b8d82d74ca5c04b644c5df07e80d6347d21b8efd01e1e37a
compiled_at: 2026-04-18T11:21:53Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: true
tags:
backlinks:
---

# Scout adoption plan

Engineering approves a full rollout of [[Scout]] to all teams by the end of Q2 2026. The rollout keeps one shared Scout instance, treats the compiled wiki as the only retrieval boundary, and adds source integrations in a staged order with explicit security and operational guardrails.

## Core framing

Scout is defined as a context agent: teams place source documents in `context/raw/`, Scout compiles them into a wiki, and specialist agents navigate that wiki to answer questions.

The group explicitly rejects framing Scout as a chatbot. The preferred framing is that Scout navigates a context graph rather than retrieving isolated chunks.

## Rollout decision

All engineering teams adopt Scout by the end of Q2 2026.

Rollout schedule:
- API is the first new team, targeted for onboarding by 2026-04-25.
- Remaining teams join in weekly cohorts through 2026-06-06.
- No team joins without a designated point person who has completed the Scout walkthrough.

A follow-up review is scheduled for 2026-04-25 at 10:00 AM to check progress and approve the API team go-live.

## Wiki boundary and editing policy

The compiled wiki is the only context surface that Navigator reads. Teams place raw documents in `context/raw/`, and Compiler writes articles to `context/compiled/articles/`.

Normal rule:
- Do not hand-edit files in `context/compiled/`.
- If an article is wrong, fix the raw source and recompile.

Exception:
- If Compiler output is materially wrong and the raw source does not explain the error, the compiled article may be edited directly.
- Scout's user-edit protection then marks the article and prevents overwrite on the next compile pass.

## Deployment model

Engineering runs one Scout instance per workspace, not one per team. A per-team split is rejected because it fragments cross-source navigation.

Workspace scoping is deferred until multi-workspace support lands via `SCOUT_WORKSPACE_ID`.

## Source integration order

The approved source sequence is:

1. **GitHub**
   - Repositories: `acme/api`, `acme/web`, `acme/infra`
   - Setup: `GITHUB_REPOS` plus a read-only PAT
   - Owner: Diego
   - Target: 2026-04-18

2. **Drive**
   - Scope: selected folders in the `Engineering` shared drive
   - Included folders: `Engineering/Handbook`, `Engineering/RFCs`, `Engineering/Postmortems`
   - Not the entire organization drive
   - Owner: Sarah
   - Target: 2026-04-22

3. **Slack**
   - Channels: `#eng`, `#eng-platform`, `#eng-api`, `#eng-incidents`
   - Mode: live-read only; threads remain in Slack
   - Owner: Nadia for scope review before install
   - Target: 2026-05-02

4. **S3**
   - Bucket: `acme-eng-archive`
   - Purpose: compile archived PDFs such as architecture diagrams, vendor contracts, and postmortem decks into wiki articles
   - Owner: Kenji
   - Target: 2026-05-09

Notion is excluded for now and will be reconsidered in July.

## Operational decisions

### Posting behavior

Scout posts scheduled output only to `#scout-updates`. This includes daily briefings, inbox digests, and weekly reviews.

Engineers may still mention Scout in any channel where Scout is installed, but Scout does not initiate posts outside `#scout-updates`.

### Compile cadence

Automatic compile runs move from every 10 minutes to every hour, on the hour. The reason is cost and churn reduction; compiled articles are not considered time-sensitive enough to justify a 10-minute cycle.

Manual recompiles remain available with:

```bash
docker exec -it scout-api python -m scout compile
```

### Voice guide

The existing `context/voice/wiki-article.md` remains the wiki style standard unchanged. The agreed standard is short, dense, and encyclopedic.

## Security and access guardrails

Gmail remains draft-only permanently. Send authority is rejected as a phishing risk, and the group confirms that Scout already excludes send capability at the code level.

Calendar access remains read-only for now. Write operations such as event creation and update are deferred until there is a clearer use case and stronger guardrails.

Private wiki article permissions are also deferred. Current policy is simple: if a source is in Scout, any user who can talk to Scout can read it. Per-document ACL enforcement may be revisited with multi-workspace support.

## Evals and CI

Evals will run in CI on every PR that touches `scout/`.

Two eval modes are defined:
- Static evals: `python -m evals`, under 90 seconds
- Live evals: `python -m evals.live`, requiring a running container and gated by label

Priya owns the CI integration, targeted for 2026-04-30.

## Rejected and deferred proposals

Rejected:
- Auto-ingesting Slack threads such as `#eng-rfc` into `context/raw/`; this is considered too noisy. Specific URLs or threads may still be ingested manually.

Deferred:
- Per-document ACL enforcement
- Fine-tuning a smaller model on the wiki
- Notion integration
- Calendar write access

The current model is considered good enough, and fine-tuning will be revisited only if cost becomes a meaningful problem.

## Action items

- Diego: wire `GITHUB_REPOS=acme/api,acme/web,acme/infra` and a read-only PAT by 2026-04-18
- Sarah: collect Drive folder IDs for Handbook, RFCs, and Postmortems by 2026-04-22
- Nadia: complete Slack install scope review and post-install audit by 2026-05-02
- Kenji: point S3 compile at `acme-eng-archive` by 2026-05-09
- Priya: add eval CI for PRs touching `scout/` by 2026-04-30
- Priya: write the Scout walkthrough required for new team onboarding by 2026-04-25
- Maya: announce the rollout and `#scout-updates` convention at all-hands by 2026-04-18
- Reza: prepare the onboarding-team adoption report for the 2026-04-25 follow-up by 2026-04-24

## Ownership

The offsite is facilitated by Maya Chen, VP Engineering. Priya Ramanathan is the scribe, and action item ownership is distributed across engineering, platform, security, and developer productivity leads.

## See also

- [[Scout]]
- [[scout-source-integrations]]
- [[scout-security-guardrails]]
- [[scout-evals]]
