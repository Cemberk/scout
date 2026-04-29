# Scout Intelligence Memory

This file is the index for Scout's institutional memory. Keep it under 200 lines.
Link to detailed topic files rather than expanding everything here.

## Quick Context

**Project**: {Project Name}
**Last Updated**: {Date}
**Primary Focus**: {Brief description}

## Key People

- **{Name}** ({Role}) - {Brief context} → [details](knowledge/people/{name}.md)
- **{Name}** ({Role}) - {Brief context} → [details](knowledge/people/{name}.md)

## Active Projects

- **{Project}** - {Status} - {One-line summary} → [details](knowledge/projects/{project}.md)
- **{Project}** - {Status} - {One-line summary} → [details](knowledge/projects/{project}.md)

## Common Patterns

### Known Issues
- **{Issue Type}** - {Brief description} → [details](knowledge/patterns/common-errors.md#issue-type)
- **{Issue Type}** - {Brief description} → [details](knowledge/patterns/common-errors.md#issue-type)

### Code Conventions
- {Convention 1} → [details](knowledge/patterns/conventions.md)
- {Convention 2} → [details](knowledge/patterns/conventions.md)

## Recent Learnings

<!-- Keep last 10-15 learnings, archive older ones to topic files -->

### {Date}: {Brief Learning}
{One sentence description}
→ Saved to: [topic file](knowledge/{category}/{file}.md)

### {Date}: {Brief Learning}
{One sentence description}
→ Related tickets: JIRA-123, JIRA-456

## Frequently Referenced

### Runbooks
- **{Procedure}** → [runbook](knowledge/runbooks/{name}.md)
- **{Procedure}** → [runbook](knowledge/runbooks/{name}.md)

### Architecture Docs
- **{System Component}** → [architecture](codebase/architecture.md#{anchor})
- **{Integration}** → [integrations](codebase/integrations.md#{anchor})

### Ticket Patterns
- **{Pattern Type}** - Seen {X} times → [pattern](tickets/patterns.md#{pattern})

## Follow-ups

<!-- Active follow-ups tracked here, use TaskCreate for time-sensitive ones -->

- [ ] {Investigation to complete}
- [ ] {Question to ask {Person}}
- [ ] {Documentation to update}

## Memory Organization

```
memory/
├── MEMORY.md                    (this file)
├── knowledge/
│   ├── people/                  (contact profiles)
│   ├── projects/                (project context)
│   ├── patterns/                (code/issue patterns)
│   └── runbooks/                (procedures)
├── tickets/
│   ├── JIRA-{ID}.md            (ticket deep-dives)
│   └── patterns.md              (ticket patterns)
└── codebase/
    ├── architecture.md          (system design)
    ├── conventions.md           (code standards)
    └── integrations.md          (external systems)
```

## Usage Notes

**When to update this file**:
- New person becomes relevant → add to Key People
- New pattern discovered → add to Common Patterns
- Important learning → add to Recent Learnings (keep last 10-15)
- New runbook created → link in Frequently Referenced

**When to create detail files**:
- Person mentioned 3+ times → create knowledge/people/{name}.md
- Pattern seen 2+ times → document in knowledge/patterns/
- Complex topic → create dedicated file, link from here

**Keep it lean**:
- This file is always loaded in context (200 line limit)
- Use links to detail files for anything beyond a one-liner
- Archive old learnings to topic files regularly

---

## Template Expansion

When Scout creates detail files, use these templates:

### Person: knowledge/people/{name}.md
```markdown
# {Name} - {Company/Role}

**Contact**: {email/slack/phone}
**Role**: {title}
**Team**: {team name}

## Context
- {How we know them}
- {Expertise areas}

## Related
- Projects: {links}
- Tickets: {links}
```

### Project: knowledge/projects/{project}.md
```markdown
# {Project Name}

**Status**: {active/blocked/complete}
**Owner**: {person}

## Overview
{What it does}

## Architecture
{Key components}

## Known Issues
- {Issue with ticket link}

## Related
- People: {stakeholders}
- Code: {repo/path}
```

### Pattern: knowledge/patterns/common-errors.md
```markdown
# Common Error Patterns

## {Error Type}

**Frequency**: {how often}
**Severity**: {impact}

### Symptoms
{What's observed}

### Root Cause
{Technical explanation}

### Resolution
{How to fix}

### Examples
- JIRA-123
- JIRA-456

### Prevention
{How to avoid}
```

### Ticket: tickets/{JIRA-ID}.md
```markdown
# {JIRA-ID}: {Title}

**Status**: {status}
**Assignee**: {person}
**Created**: {date}

## Problem
{Description}

## Resolution
{What was done}

## Related
- Similar: JIRA-{other}
- Pattern: [link to pattern](../knowledge/patterns/common-errors.md#{pattern})
```
