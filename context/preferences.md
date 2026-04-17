---
tags: [team-preferences]
---

# Preferences

## Basics

- Timezone: US/Eastern (EST/EDT)
- Working hours: Mon–Fri, 9:00–18:00
- Preferred units: imperial
- Preferred spelling: US

## Default response style

- Concision: concise
- Structure: bullets first
- Dates: always use exact dates (e.g., 2026-03-03) when scheduling or referencing time
- Action items: include owner + due date when relevant

## Writing preferences

- Emoji: avoid
- Tone: direct, professional
- "No-go" phrases: "circle back", "synergy", "leverage", "touch base", "at the end of the day"

## File conventions (when Scout writes files)

- Meeting notes path: `context/meetings/`
- Meeting notes filename: `YYYY-MM-DD - meeting - topic.md`
- Weekly review path: `context/meetings/`
- Weekly review filename: `YYYY-MM-DD - weekly-review.md`
- Project docs path: `context/projects/`
- Project doc filename: `project - <name>.md`

## Scheduled tasks

Scout runs these automatically — no prompting required:

| Task | Schedule | What it does |
|------|----------|-------------|
| Context refresh | 8 AM daily | Re-index context files into knowledge |
| Daily briefing | 8 AM weekdays | Calendar, emails, priorities |
| Wiki compile | 9 AM daily | Compile new raw sources into wiki articles |
| Inbox digest | 12 PM weekdays | Midday email digest, flag responses |
| Learning summary | 10 AM Monday | Summarize patterns from scout_learnings |
| Weekly review | 5 PM Friday | Fill weekly-review template, save to meetings/ |
| Wiki lint | 8 AM Sunday | Wiki health check — find gaps and issues |
| Sync pull | Every 30 min | Pull remote context/ changes from GitHub |

If a scheduled task produces a file, follow the file conventions above.

## Slack channels

| Channel | Purpose |
|---------|---------|
| #scout-updates | All scheduled task posts (briefings, digests, reviews, summaries) |

## Governance

- Always confirm before: creating events with external attendees, drafting external emails
- Never do: send emails directly, delete files, drop database tables without confirmation
