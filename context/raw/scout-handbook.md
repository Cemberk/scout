---
title: "Scout Handbook"
source: local
fetched_at: 2026-04-21
tags: [scout, handbook, onboarding]
type: handbook
---

# Scout Handbook

Scout is a four-role enterprise context agent: Explorer reads, Engineer writes, Doctor diagnoses, and the Leader coordinates and handles outbound (Slack, Gmail, Calendar).

## Getting started

Drop files into `context/raw/` and ask Engineer to ingest and compile — or run `python -m scout compile`. Compiled articles land in `context/compiled/` and become queryable through the wiki.

## Who to ask what

- **Explorer** — any question. Fans out across the wiki + registered contexts.
- **Engineer** — "ingest X", "add a contact", "compile the wiki", schema changes.
- **Doctor** — health, diagnostics, "why is this context disconnected?"
