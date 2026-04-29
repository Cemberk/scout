# Scout Intelligence Orchestration - CLAUDE.md Template

This is a template for projects that want to use the `/scout` skill for organizational intelligence.

Copy this to your project's `CLAUDE.md` or adapt sections as needed.

---

## Organizational Context

**Company**: {Your Organization}
**Primary Systems**:
- Jira: {instance URL} - via Jira MCP
- CRM: {system name} - via {MCP name}
- Wiki: {Confluence/Notion/etc} - via {MCP name}
- Slack: {workspace} - via Slack MCP

**MCP Servers Connected**:
```bash
# Check with:
# /mcp list
# or use ListMcpResourcesTool

Expected MCPs:
- jira (or organization_jira)
- crm (or salesforce/hubspot/etc)
- confluence (or wiki/notion/etc)
- slack
- code_generation (optional - AMD-specific)
- nabu (optional - AMD-specific knowledge base)
```

## Scout Usage Patterns

### Default Behavior

When users ask about organizational context, automatically use `/scout`:

**Trigger phrases**:
- "Find ticket/issue/JIRA..."
- "Who works on..."
- "Similar issues..."
- "Latest discussion about..."
- "Save this to memory..."
- "Document this codebase..."
- "What's the status of..."

**Process**:
1. Invoke `/scout {query}`
2. Let Scout orchestrate the MCP calls
3. Scout will save findings to project memory
4. Scout will create follow-up tasks if needed

### Memory Organization

Scout maintains memory in `.claude/projects/{project}/memory/`:

```
memory/
├── MEMORY.md                    # Main index (< 200 lines)
├── knowledge/
│   ├── people/{person}.md       # Contact profiles
│   ├── projects/{project}.md    # Project context
│   ├── patterns/                # Code/issue patterns
│   └── runbooks/                # Procedures
├── tickets/
│   ├── {JIRA-ID}.md            # Ticket context
│   └── patterns.md              # Ticket patterns
└── codebase/
    ├── architecture.md          # System design
    ├── conventions.md           # Code standards
    └── integrations.md          # External systems
```

**IMPORTANT**:
- Always check existing memory before querying external sources
- Update memory when learning new information
- Link related concepts (person → project → ticket)

### Routing Examples

**Code Questions** → Scout uses codebase tools + checks Jira for related tickets:
```
Q: "Why is this authentication flow so complex?"
Scout → Grep for auth patterns → Read relevant files →
        Check Jira for auth-related tickets →
        Check Confluence for auth docs →
        Synthesize answer + save pattern
```

**People Questions** → Scout uses CRM + Jira + Slack:
```
Q: "Who should review this database change?"
Scout → Check memory/knowledge/people/ for database experts →
        Search Jira for recent DB-related tickets (get assignees) →
        Search Slack #database channel for active participants →
        Check CRM for team structure →
        Answer with specific people + reasoning
```

**Debugging** → Scout uses multi-source approach:
```
Q: "This query is timing out, has anyone seen this before?"
Scout → Check memory/patterns/common-errors.md →
        Search Jira for "timeout" + component →
        Grep codebase for similar queries →
        Search Slack for recent timeout discussions →
        Use Code Generation MCP if available →
        Synthesize findings + save pattern if new
```

**Knowledge Building** → Scout creates hierarchical documentation:
```
Q: "Document this service's architecture"
Scout → Glob directory structure →
        Read main entry points + configs →
        Grep for key patterns (APIs, schemas, integrations) →
        Search Jira for architectural tickets →
        Search Confluence for existing docs →
        Write to memory/codebase/architecture.md →
        Create follow-up tasks for gaps
```

## Integration with Development Workflow

### When fixing bugs:
1. Use `/scout find similar issues to {description}`
2. Scout will check Jira + codebase + Slack
3. Scout saves the pattern to memory
4. When you fix it, update memory with resolution

### When working on features:
1. Use `/scout who works on {component}?`
2. Scout finds stakeholders and context
3. Use `/scout latest discussion about {topic}`
4. Scout synthesizes from Slack + Jira + Confluence

### When onboarding to new code:
1. Use `/scout build knowledge base from this codebase`
2. Scout creates hierarchical documentation
3. Links to Jira tickets, docs, discussions
4. Saves to memory for future reference

### When investigating incidents:
1. Use `/scout find timeline of {incident}`
2. Scout searches Jira + Slack + monitoring (if MCP available)
3. Creates runbook in memory if pattern is repeatable

## Scout + Other Tools

Scout orchestrates, but doesn't replace direct tool use:

**Use Scout When**:
- Multi-source investigation needed
- Building/updating institutional memory
- Finding people or context
- Pattern matching across tickets/code

**Use Direct Tools When**:
- Single source, straightforward query
- Just need raw data (no synthesis)
- Interactive exploration (Scout is for retrieval + synthesis)

**Examples**:

✅ Use Scout: "Find all authentication-related issues from the last quarter"
→ Multi-source (Jira + code + Slack), needs synthesis

❌ Don't use Scout: "Read src/auth.py"
→ Single source, direct read

✅ Use Scout: "Who worked on the payment integration and what decisions did they make?"
→ Multi-source (Jira + CRM + Slack + Confluence), needs context building

❌ Don't use Scout: "Create a new ticket in Jira"
→ Single operation, use Jira MCP directly

## Customization

### Project-Specific Routing

Override Scout's default routing for your project:

```markdown
## Project-Specific Scout Behavior

For this project (Project X):

1. Authentication questions should ALWAYS check memory/runbooks/auth.md first
2. Database questions should mention Alice (DBA) in the response
3. Frontend questions should check #frontend-guild in Slack
4. All API changes should create a follow-up task to update Confluence
```

### Custom Memory Templates

If your organization has specific formats:

```markdown
## Custom Templates for Project X

### Incident Report
Use this template in memory/incidents/{date}-{summary}.md:
- Timestamp
- Severity
- Root Cause
- Resolution
- Prevention
- Related Tickets
```

### Team Preferences

```markdown
## Team Preferences

- Save ticket context immediately when referenced
- Always link to Confluence docs when available
- Create follow-up tasks for "TODO" items in conversations
- Notify in response when creating new memory files
```

## Best Practices

1. **Trust the Navigation Pattern**: Let Scout navigate hierarchically, don't pre-fetch everything
2. **Keep Memory Current**: Update memory files when learning new information
3. **Link Everything**: People → Projects → Tickets → Code
4. **Be Specific**: "Find auth issues" is better than "Find issues"
5. **Check Memory First**: Always consult memory before external queries
6. **Save Learnings**: When Scout discovers something useful, ensure it's saved to memory
7. **Create Follow-ups**: Use TaskCreate for pending investigations

## Troubleshooting

### Scout isn't using the right MCP
Check which MCPs are connected:
```
/mcp list
```
Or use `ListMcpResourcesTool` to verify

### Scout isn't saving to memory
Verify memory directory exists:
```
ls .claude/projects/{project}/memory/
```

### Scout is too verbose
Add to CLAUDE.md:
```
Scout responses should be 2-3 sentences max unless asked for details.
```

### Scout isn't checking memory first
Remind in conversation:
```
Check memory first before querying external sources.
```
Or add to CLAUDE.md as default behavior.

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `/scout {query}` | General intelligence query |
| `/scout find similar issues to JIRA-123` | Pattern matching |
| `/scout who works on {component}?` | Find people/expertise |
| `/scout save this to memory` | Explicit memory save |
| `/scout build knowledge base` | Document codebase |
| `/scout latest on {topic}` | Multi-source synthesis |

All queries automatically:
- Check memory first
- Use appropriate MCPs
- Synthesize findings
- Save learnings
- Create follow-ups

---

**Remember**: Scout is orchestration logic. The value is in the navigation pattern, routing intelligence, and memory building - not the code itself.
