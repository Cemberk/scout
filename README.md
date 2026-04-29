# Scout - Company Intelligence Skill for Claude Code

Scout is a Claude Code skill that orchestrates organizational intelligence gathering across multiple sources.

**Navigation over search.** Scout navigates hierarchically (like coding agents: `ls`, `grep`, open file) rather than ingesting everything into vector databases.

**Multi-source synthesis.** Scout combines information from Jira, CRM, Slack, Wiki, codebase, and web to answer questions with full context.

**Institutional memory.** Scout builds and maintains knowledge bases in `.claude/projects/{project}/memory/` as it learns about your company, codebase, and team.

## What Scout Does

- 🔍 **Find similar tickets** - Patterns from Jira/Linear + codebase + past resolutions
- 👥 **Find expertise** - Who works on what, from tickets + CRM + Slack activity
- 📚 **Build knowledge bases** - Hierarchical codebase documentation with context
- 🐛 **Debug with context** - Check known issues, similar patterns, recent discussions
- 💾 **Persistent memory** - Save error patterns, people profiles, project context
- 📋 **Follow-up tracking** - Create tasks for pending investigations

## How It Works

Scout is **pure orchestration logic** - no Python code required:

```
User Query
    ↓
Scout Skill (routing logic)
    ↓
MCP Servers (Jira, Slack, CRM, Wiki)
    ↓
Claude Code Tools (Glob, Grep, Read)
    ↓
Memory Files (.claude/projects/{project}/memory/)
    ↓
Synthesized Answer + Saved Knowledge
```

## Prerequisites

**Required**:
- Claude Code CLI
- At least one organizational MCP server (Jira, Linear, GitHub Issues, etc.)

**Recommended MCP Servers**:
- Jira/Linear/Issue Tracker
- Slack
- Confluence/Notion/Wiki
- Internal CRM

Check what's connected:
```bash
/mcp list
```

## Installation

### Via Claude Code Plugin (Recommended)

```bash
/plugin marketplace add Cemberk/scout
/plugin install scout@cemberk-scout
```

This auto-installs the skill globally for use in all your projects.

### Manual Installation

#### Global (Available in all projects)

```bash
# Linux/Mac
cp .claude/skills/scout.md ~/.claude/skills/

# Windows
copy .claude\skills\scout.md %USERPROFILE%\.claude\skills\
```

#### Project-Specific

```bash
cp .claude/skills/scout.md {your-project}/.claude/skills/
```

See [SKILL_SETUP.md](.claude/SKILL_SETUP.md) for detailed setup.

## Quick Start

### 1. Install the plugin

```bash
# In Claude Code
/plugin marketplace add Cemberk/scout
/plugin install scout@cemberk-scout
```

Or manually:
```bash
cp .claude/skills/scout.md ~/.claude/skills/
```

### 2. Initialize project memory

```bash
cd {your-project}
mkdir -p .claude/projects/{project}/memory/{knowledge/{people,projects,patterns,runbooks},tickets,codebase}
cp {scout-install-dir}/memory-template/MEMORY.md .claude/projects/{project}/memory/
```

### 3. Add to CLAUDE.md (optional)

```markdown
## Scout Intelligence

Use `/scout` for organizational context queries.

Examples:
- `/scout find similar issues to authentication timeout`
- `/scout who works on the payment service?`
- `/scout build knowledge base from this codebase`
```

### 4. Use it

```bash
# In Claude Code session
/scout find similar issues to: API returns 503 under high load
/scout who should review this database migration?
/scout build knowledge base from this codebase
```

## Usage Examples

### Finding Similar Issues

```bash
/scout find similar issues to: API returns 503 under high load
```

Scout will:
1. Check `memory/patterns/common-errors.md` for known patterns
2. Search Jira for "503" + "high load" tickets
3. Use Code Generation MCP's `similar_tickets_search` if available
4. Grep codebase for similar error handling
5. Synthesize findings and save pattern if new

### Finding People/Expertise

```bash
/scout who should review this database migration?
```

Scout will:
1. Check `memory/knowledge/people/` for database experts
2. Search Jira for recent DB-related tickets → get assignees
3. Search Slack #database for active contributors
4. Check CRM for team structure
5. Provide specific people with reasoning

### Building Knowledge Base

```bash
/scout build knowledge base from this codebase
```

Scout will:
1. Glob directory structure
2. Read configs, entry points, key files
3. Grep for patterns (APIs, schemas, integrations)
4. Search Jira for related tickets
5. Search Wiki for existing docs
6. Write hierarchical docs to `memory/codebase/`
7. Create follow-up tasks for gaps

### Debugging with History

```bash
/scout this query is timing out, has anyone seen this before?
```

Scout will:
1. Check memory for similar issues
2. Search Jira for timeout tickets in this component
3. Grep codebase for similar queries
4. Search Slack for recent discussions
5. Synthesize findings with links
6. Save pattern with resolution

## Memory Organization

Scout maintains memory in `.claude/projects/{project}/memory/`:

```
memory/
├── MEMORY.md                    # Main index (< 200 lines)
├── knowledge/
│   ├── people/                  # Contact profiles
│   ├── projects/                # Project context
│   ├── patterns/                # Code/issue patterns
│   └── runbooks/                # Procedures
├── tickets/
│   ├── JIRA-{ID}.md            # Ticket deep-dives
│   └── patterns.md              # Common ticket patterns
└── codebase/
    ├── architecture.md          # System design
    ├── conventions.md           # Code standards
    └── integrations.md          # External systems
```

**Key principles**:
- MEMORY.md is always loaded (keep under 200 lines)
- Link to detail files for deep-dives
- Update as you learn
- Connect related concepts (person → project → ticket → code)

## Routing Logic

Scout automatically routes to the right sources:

| Query Type | Tools Used |
|------------|------------|
| "Find ticket/issue" | Jira MCP → Memory → Codebase |
| "Who works on X?" | CRM → Jira → Slack → Memory |
| "How does X work?" | Codebase (Glob/Grep/Read) → Wiki → Memory |
| "Latest on X" | WebSearch → Slack → Jira |
| "Similar issues?" | Jira → Memory → Code Gen MCP |
| "Debug error" | Memory → Jira → Codebase → Slack |

See [scout.md](.claude/skills/scout.md) for full routing table.

## Customization

### Project-Specific Routing

Add to your project's `CLAUDE.md`:

```markdown
## Scout Behavior for This Project

For authentication questions:
1. Always check memory/runbooks/auth.md first
2. Mention Alice (Security Lead) in findings
3. Link to Confluence auth documentation

For database questions:
1. Check memory/codebase/schema.md
2. Tag Bob (DBA) in follow-up tasks
3. Search #database Slack channel
```

### Custom Templates

Scout uses standard templates (see [MEMORY.md](.claude/memory-template/MEMORY.md)), but you can override:

```markdown
## Custom Memory Templates

### Incident Report Template
Use in memory/incidents/{date}-{summary}.md:
- Timestamp: {ISO 8601}
- Severity: {P0/P1/P2}
- Root Cause: {technical explanation}
- Resolution: {what fixed it}
- Prevention: {how to avoid}
- Related: {ticket links}
```

## Integration with Workflow

**Code Review**:
```bash
/scout find tickets related to this authentication change
/scout who worked on similar auth updates?
```

**Debugging**:
```bash
/scout has anyone seen this error before?
/scout save this error pattern
```

**Onboarding**:
```bash
/scout build knowledge base from this codebase
/scout who are the key people on this team?
```

**Planning**:
```bash
/scout what's the status of the payment integration?
/scout latest discussion about API v2 migration
```

## Architecture

Scout collapses the original [Scout Python implementation](https://github.com/agno-agi/scout) into pure orchestration:

**Original Scout** (Python):
- FastAPI server + AgentOS
- Context providers (Web, Slack, Drive, CRM, Wiki, MCP)
- Sub-agents for each provider
- Persistent database
- Scheduled tasks

**Scout Skill** (Orchestration):
- ✅ Routing logic → Skill definition
- ✅ Context providers → MCP servers
- ✅ Sub-agents → Claude Code's tool delegation
- ✅ Persistent memory → `.claude/projects/{project}/memory/`
- ✅ Scheduled tasks → TaskCreate/CronCreate
- ✅ Navigation patterns → Preserved in instructions

**Same intelligence, zero code deployment.**

## Documentation

- [SKILL_SETUP.md](.claude/SKILL_SETUP.md) - Detailed installation guide
- [CLAUDE_SKILL.md](.claude/CLAUDE_SKILL.md) - CLAUDE.md template for projects
- [scout.md](.claude/skills/scout.md) - The skill definition
- [MEMORY.md](.claude/memory-template/MEMORY.md) - Memory template

## Examples

### Multi-Source Investigation

**Query**: "Why is authentication so complex in this codebase?"

**Scout's Process**:
1. ✅ Grep codebase for auth patterns
2. ✅ Read auth-related files
3. ✅ Search Jira for auth architecture tickets
4. ✅ Check Confluence for auth documentation
5. ✅ Search Slack #security for recent discussions
6. ✅ Synthesize: "Auth uses OAuth2 + custom JWT validation (JIRA-1234). Complex because of legacy SSO integration (see Confluence: Auth Architecture). Recent discussion in #security about simplifying..."
7. ✅ Save pattern to memory/patterns/auth.md

### Knowledge Base Building

**Query**: "/scout build knowledge base from this codebase"

**Scout's Output**:
```
Created hierarchical documentation:

memory/codebase/architecture.md:
- Service structure (API, Workers, DB)
- Data flow diagrams
- External integrations (Stripe, Auth0)
- Links to: JIRA-456 (architecture decision), Confluence (design doc)

memory/codebase/conventions.md:
- File naming: camelCase for components, snake_case for utilities
- Testing: Jest + Playwright, 80% coverage target
- Error handling: Custom AppError class (see src/errors.ts)

memory/codebase/integrations.md:
- Stripe API (payment processing)
- Auth0 (authentication)
- SendGrid (email)
- Links to API docs and setup guides

Created 3 follow-up tasks:
- Document the worker queue system (gap in arch docs)
- Update testing conventions (Playwright recently added)
- Link to deployment runbook (mentioned in Slack but not documented)
```

## Troubleshooting

**Scout doesn't work**:
- Check skill is installed: `ls ~/.claude/skills/scout.md`
- Check MCPs connected: `/mcp list`

**Scout isn't using right MCP**:
- Verify MCP name: `/mcp list | grep jira`
- Update CLAUDE.md if different name

**Scout isn't saving to memory**:
- Check directory exists: `ls .claude/projects/{project}/memory/`
- Create if missing: `mkdir -p .claude/projects/{project}/memory/...`

**Scout is too verbose**:
- Add to CLAUDE.md: `Scout responses: 2-3 sentences max unless asked for details`

See [SKILL_SETUP.md](.claude/SKILL_SETUP.md) for more troubleshooting.

## Credits

Based on [Scout](https://github.com/agno-agi/scout) by [Agno](https://github.com/agno-agi).

Original implementation: Python + AgentOS + Context Providers

This skill: Pure orchestration logic for Claude Code

## License

MIT - See [LICENSE](LICENSE)

---

**Remember**: Scout is orchestration logic. The value is in the navigation pattern, routing intelligence, and memory building - not the implementation code.
