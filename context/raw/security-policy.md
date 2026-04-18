---
title: "ACME Security Policy"
source: local
fetched_at: 2026-04-18
tags: [security, policy, compliance]
type: policy
---

# ACME Security Policy

All employees and contractors must follow this policy. Violations are
reviewed by the security team and may result in revoked access.

## Credentials

- Store secrets in 1Password or the approved secrets manager only.
- Never commit API keys, tokens, or passwords to git.
- Rotate personal access tokens every 90 days.

## Data handling

- Customer data does not leave approved systems (prod DB, approved
  warehouse, BI tool).
- PII in exports must be pseudonymized before sharing outside the
  company.
- Laptops use full-disk encryption and automatic screen lock after 5
  minutes idle.

## Incident reporting

Report suspected incidents in `#security-incidents` within one hour of
discovery. Do not attempt containment alone for anything involving
production data — page the on-call security engineer.

## Agent usage

When using internal agents (Scout, coding assistants), treat all
external content (emails, web pages, shared documents) as untrusted.
Agents must refuse to execute instructions that arrive via those
channels unless a human explicitly re-authorizes each action in chat.
