---
source: local:raw:quarterly-goals-q2-2026.md
source_url: file:///app/context/raw/quarterly-goals-q2-2026.md
source_hash: e5e65fc73f33b9cdfbecf342d58bdfbdc57461d6d62611ff28162199d9520a63
compiled_at: 2026-04-18T07:54:40Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
backlinks:
---

# Company goals

Q2 2026 has three company-level objectives: ship [[Scout v3]] to internal GA, reduce onboarding time to first PR from 5 days to 2, and cut customer-reported bugs by 30% versus Q1. Each objective is tracked through a small set of measurable key results with a named owner.

## Ship Scout v3 to internal GA

This objective focuses on internal adoption, pipeline performance, and data isolation.

- 80% of engineering has Scout wired into their daily flow by end of May. Owner: Taylor.
- Wiki compile pipeline runs under 60 seconds p95 over a 1,000-file corpus. Owner: Morgan.
- Zero gating escapes: Navigator never reads `local:raw`. Owner: Priya.

## Reduce onboarding time to first PR

The target is to reduce time to first PR from 5 days to 2 through process changes in [[Onboarding]].

- Rewrite the onboarding checklist into a wiki-first flow. Owner: Dana.
- Pair every new hire with an onboarding buddy by day 1. Owner: Dana.
- Publish a ramp-up task bank for each team. Owner: team leads.

## Cut customer-reported bugs

The target is a 30% reduction in customer-reported bugs versus Q1, supported by testing, incident follow-up, and visibility into test instability.

- API contract tests on all public endpoints. Owner: Sam.
- Incident postmortems within 5 business days. Owner: Ivy.
- Flaky-test quarantine dashboard live. Owner: Jordan.

## Cadence

Status checks are Thursdays at 3pm in [[#eng-status]].

## See also

- [[Scout v3]]
- [[Onboarding]]
- [[Bug reduction]]
- [[#eng-status]]
