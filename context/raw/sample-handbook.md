---
title: "ACME Sample Handbook"
source: local
fetched_at: 2026-04-18
tags: [sample, handbook, pto, onboarding]
type: handbook
---

# ACME Sample Handbook

This is a seed document so the Compiler has something to compile on first
boot. Drop your own docs into `context/raw/` to replace it — the same
pipeline applies to every file.

## PTO Policy

Full-time ACME employees receive 25 days of paid time off per calendar
year, plus 11 public holidays. PTO accrues at 2.08 days per month and
rolls over up to 5 days into the following year.

### Eligibility

All full-time employees from their first day. Contractors and part-time
employees follow the contractor-leave policy.

### Requesting time off

Submit via Workday at least two weeks before the intended start date
for absences of three days or more. Shorter absences may be requested
with 48 hours' notice.

## Public Holidays

ACME observes 11 US federal holidays:

- New Year's Day
- Martin Luther King Jr. Day
- Presidents' Day
- Memorial Day
- Juneteenth
- Independence Day
- Labor Day
- Columbus Day
- Veterans Day
- Thanksgiving
- Christmas Day

## Onboarding

New hires follow a 30/60/90-day plan:

1. **Week 1**: laptop setup, tooling install, introductions with the
   direct team.
2. **Week 2–4**: shadow a senior engineer, read internal runbooks,
   complete the security training.
3. **Month 2**: own a small feature end-to-end, present at the weekly
   demo.
4. **Month 3**: take on-call rotation, own a larger area.

Owner: People Ops (people@acme.example).

## Deploy Runbook

All production deploys go through the `deploy` GitHub Action on the
`main` branch. Rollback is a single-click action on the last-green
deploy in the dashboard. Incidents of Sev-2 or higher page the on-call
engineer via PagerDuty.

See also: on-call rotation policy, incident response procedure.
