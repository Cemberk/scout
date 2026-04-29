# Scout Skill Setup Guide

This guide shows how to install the Scout intelligence orchestration skill in any Claude Code project.

## What You Get

A single `/scout` skill that:
- ✅ Orchestrates multiple MCP servers (Jira, CRM, Slack, Wiki, etc.)
- ✅ Navigates hierarchically (like coding agents: targeted, not broad)
- ✅ Builds institutional memory in `.claude/projects/{project}/memory/`
- ✅ Creates follow-up tasks for pending work
- ✅ Synthesizes multi-source intelligence
- ✅ Documents codebases automatically

**No Python code needed** - just orchestration logic in a skill definition.

## Prerequisites

You need MCP servers connected for organizational data:

**Required**:
- At least one organizational MCP (Jira, Linear, GitHub Issues, etc.)

**Recommended**:
- Jira/Linear/Issue Tracker MCP
- Slack MCP
- Wiki/Confluence/Notion MCP
- Internal CRM MCP (if available)

**Optional**:
- Code Generation MCP (for advanced code analysis)
- Nabu MCP (if using AMD's knowledge base)
- Custom organizational MCPs

Check what's connected:
```bash
/mcp list
# or in code:
# Use ListMcpResourcesTool
```

## Installation

### Option 1: Global Skill (Available in all projects)

Copy the skill to your global skills directory:

```bash
# Linux/Mac
cp scout/.claude/skills/scout.md ~/.claude/skills/

# Windows
copy scout\.claude\skills\scout.md %USERPROFILE%\.claude\skills\
```

### Option 2: Project-Specific Skill

Copy to your project's `.claude/skills/` directory:

```bash
mkdir -p .claude/skills/
cp {path-to-scout}/.claude/skills/scout.md .claude/skills/
```

### Option 3: Symlink (for development)

```bash
# Linux/Mac
ln -s {path-to-scout}/.claude/skills/scout.md ~/.claude/skills/scout.md

# Windows (requires admin)
mklink %USERPROFILE%\.claude\skills\scout.md {path-to-scout}\.claude\skills\scout.md
```

## Project Setup

### 1. Initialize Memory Structure

In your project directory:

```bash
mkdir -p .claude/projects/{project-name}/memory/{knowledge/{people,projects,patterns,runbooks},tickets,codebase}
```

Or let Scout create it on first use.

### 2. Copy Memory Template (Optional)

```bash
cp {path-to-scout}/.claude/memory-template/MEMORY.md .claude/projects/{project-name}/memory/
```

### 3. Add Scout Instructions to CLAUDE.md

Add this to your project's `CLAUDE.md`:

```markdown
## Intelligence Gathering with Scout

Use the `/scout` skill for organizational context:

**Trigger phrases**:
- "Find ticket/issue/JIRA..."
- "Who works on..."
- "Similar issues..."
- "Document this codebase..."

**Examples**:
- `/scout find similar issues to authentication timeout`
- `/scout who works on the payment service?`
- `/scout build knowledge base from this codebase`
- `/scout save this error pattern`

**Memory Location**: `.claude/projects/{project-name}/memory/`

Scout automatically:
- Checks memory first
- Uses appropriate MCPs
- Synthesizes findings
- Saves learnings
- Creates follow-up tasks
```

Or copy the full template from `.claude/CLAUDE_SKILL.md` and customize.

## Verification

Test the installation:

```bash
# In Claude Code session:
/scout
# Should show: "I'm Scout, a company intelligence agent..."

# Test with a query:
/scout find all tickets about authentication
# Should use Jira MCP + check memory + synthesize results

# Test memory:
/scout save this to memory: The API uses JWT tokens for auth
# Should create/update memory file

# Check memory was created:
ls .claude/projects/{project-name}/memory/
```

## Configuration

### Set Your Organization Context

Edit your project's `CLAUDE.md`:

```markdown
## Organizational Context

**Company**: {Your Organization}
**Jira**: {instance URL}
**Slack**: {workspace}
**Wiki**: {Confluence/Notion instance}

**Connected MCPs**:
- jira
- slack
- confluence
- {your-org-crm}
```

### Customize Routing

Override default routing for your needs:

```markdown
## Scout Routing for This Project

For authentication questions:
1. Check memory/runbooks/auth.md first
2. Then search Jira for auth-related tickets
3. Check Slack #security channel
4. Always mention Alice (Security Lead) in findings

For database questions:
1. Check memory/codebase/architecture.md for schema
2. Search Jira for DB performance tickets
3. Tag Bob (DBA) in follow-up tasks
```

### Set Memory Preferences

```markdown
## Scout Memory Preferences

- Save ticket context immediately when referenced (don't ask)
- Always link Confluence docs when available
- Create follow-up tasks for TODOs
- Notify when creating new memory files
- Use terse responses (2-3 sentences default)
```

## Usage Examples

### Finding Similar Issues

```bash
/scout find similar issues to: API returns 503 under high load
```

Scout will:
1. Check `memory/patterns/common-errors.md`
2. Search Jira for "503" + "high load" + related components
3. Use Code Generation MCP's `similar_tickets_search` if available
4. Synthesize findings
5. Save pattern if new

### Finding People/Expertise

```bash
/scout who should review this database migration?
```

Scout will:
1. Check `memory/knowledge/people/` for database experts
2. Search Jira for recent DB-related tickets → get assignees
3. Search Slack #database for active contributors
4. Check org CRM for team structure
5. Synthesize: "Alice (DBA, 15 DB tickets this quarter)..."

### Building Knowledge Base

```bash
/scout build knowledge base from this codebase
```

Scout will:
1. Glob directory structure
2. Read package manifests, configs, entry points
3. Grep for key patterns (APIs, schemas, tests)
4. Search Jira for architecture tickets
5. Search Wiki for existing docs
6. Write hierarchical documentation to `memory/codebase/`
7. Create follow-up tasks for gaps

### Debugging with Context

```bash
/scout this query is timing out, has anyone seen this before?
```

Scout will:
1. Check `memory/patterns/common-errors.md`
2. Search Jira for "timeout" + related component
3. Grep codebase for similar queries
4. Search Slack for recent timeout discussions
5. Synthesize findings
6. Save pattern with resolution

## Advanced: Multi-Project Intelligence

Scout can work across projects if memory is organized properly:

```bash
# Project A
.claude/projects/project-a/memory/
├── MEMORY.md
└── knowledge/people/alice.md

# Project B (can reference Project A's findings)
.claude/projects/project-b/memory/
├── MEMORY.md
└── knowledge/
    └── related-projects.md  # Links to ../project-a findings
```

Cross-reference in CLAUDE.md:

```markdown
## Related Projects

This project uses authentication from Project A.
See: `.claude/projects/project-a/memory/knowledge/patterns/auth.md`
```

## Troubleshooting

### Scout doesn't work

**Check skill is installed**:
```bash
ls ~/.claude/skills/scout.md
# or
ls .claude/skills/scout.md
```

**Check MCPs are connected**:
```bash
/mcp list
```

### Scout isn't using the right MCP

**Verify MCP name**:
```bash
/mcp list | grep jira
# Should show: "jira" or "organization_jira" etc.
```

**Update routing in CLAUDE.md** if MCP has different name:
```markdown
Scout should use "organization_jira" MCP for ticket queries.
```

### Scout isn't saving to memory

**Check directory exists**:
```bash
ls -la .claude/projects/{project-name}/memory/
```

**Create if missing**:
```bash
mkdir -p .claude/projects/{project-name}/memory/knowledge/{people,projects,patterns,runbooks}
mkdir -p .claude/projects/{project-name}/memory/{tickets,codebase}
```

### Scout is too verbose

Add to CLAUDE.md:
```markdown
Scout responses: 2-3 sentences max unless asked for details.
```

### Scout isn't checking memory first

Add to CLAUDE.md:
```markdown
CRITICAL: Scout must ALWAYS check memory files before querying external sources.
```

## Next Steps

1. **Test with real queries** - Try finding tickets, people, patterns
2. **Build initial memory** - Document your codebase with `/scout build knowledge base`
3. **Establish patterns** - As you fix bugs, save patterns with `/scout save this error pattern`
4. **Refine routing** - Customize CLAUDE.md based on team workflow
5. **Scale memory** - Keep MEMORY.md under 200 lines, link to detail files

## Integration with Workflow

**During code review**:
```bash
/scout find tickets related to this authentication change
/scout who worked on similar auth updates?
```

**During debugging**:
```bash
/scout has anyone seen this error before?
/scout save this error pattern: {description}
```

**During onboarding**:
```bash
/scout build knowledge base from this codebase
/scout who are the key people on this team?
```

**During planning**:
```bash
/scout what's the status of the payment integration?
/scout latest discussion about API v2 migration
```

---

## Summary

Scout is **orchestration logic**, not code:
- ✅ Skill definition = routing + navigation patterns
- ✅ CLAUDE.md = project-specific behavior
- ✅ Memory = institutional knowledge persistence
- ✅ MCPs = data sources
- ✅ Claude Code tools = codebase navigation

**The value is in the pattern**: navigation over search, multi-source synthesis, progressive memory building.

All functionality from the original Scout Python codebase, but collapsed into a single skill that orchestrates existing tools.
