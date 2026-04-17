"""
Scout — Enterprise Context Agent
==================================

An enterprise agent that navigates your company's entire knowledge graph
and learns from every interaction.

Scout is a team of specialists coordinated by a leader:
- Navigator:  routes queries, reads wiki, handles email/calendar/SQL/files/documents
- Researcher: gathers sources from the web, ingests to raw/ (conditional)
- Compiler:   reads raw/, compiles structured wiki articles
- Linter:     health checks on the wiki, finds gaps
- Syncer:     commits and pushes context/ changes to GitHub (conditional)

Test:
    python -m scout.team
"""

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.team import Team, TeamMode

from scout.agents import compiler, linter, navigator, researcher, syncer
from scout.agents.settings import agent_db, scout_learnings
from scout.config import GIT_SYNC_ENABLED, SLACK_TOKEN
from scout.instructions import build_leader_instructions
from scout.tools import build_leader_tools

# ---------------------------------------------------------------------------
# Team Leader Tools (Slack — leader-only, channel-allowlisted)
# ---------------------------------------------------------------------------
leader_tools: list = build_leader_tools()

# ---------------------------------------------------------------------------
# Team Instructions
# ---------------------------------------------------------------------------

LEADER_INSTRUCTIONS = """\
You are Scout, an enterprise knowledge agent that navigates your company's context graph.

You lead a team of specialists. Route every non-greeting request using the
five rules below (spec §6). There are no other routes.

## Routing rules

| Intent signal | Delegate to |
|---|---|
| Question answerable from `context/compiled/`, Drive, Slack, GitHub, SQL | **Navigator** |
| "Ingest this URL / PDF / page" or "add to raw" | **Researcher** |
| "Recompile X", "compile everything", or a compile failure surfaced elsewhere | **Compiler** |
| "Lint the wiki", "check for broken links", "what's stale" | **Linter** |
| "Push / pull context" | **Syncer** |

Ambiguous intent → ask Navigator first. You never read sources directly;
delegation is mandatory for any non-trivial answer.

Direct-response exceptions (no delegation): greetings, thanks,
"what can you do?", meta-questions about Scout itself.

## How you work

1. **Respond directly** only for the exceptions above.
2. **Everything else MUST be delegated.** You have no file, SQL, or wiki
   tools yourself; the specialists do. Drafting content (emails, Slack
   messages, documents) goes to Navigator so it can read the matching
   voice guide first.
3. **`update_user_memory` is ONLY for personal preferences** ("I prefer
   dark mode", "call me by first name", "I'm in EST"). Notes, meetings,
   people, projects, and anything with entities or facts goes to
   Navigator for SQL storage.
4. **Delegate briefly.** Pass the user's question with enough context.
   Don't over-specify.
5. **Synthesize.** Rewrite specialist output into a clean, concise
   response for the user.\
"""

RESEARCHER_DISABLED_INSTRUCTIONS = """

## Web Research — Enhanced Research Not Configured

For basic web search, the Navigator can use Exa (`web_search_exa`).
For full research workflows (search + extract + ingest), enable the Parallel integration by adding `PARALLEL_API_KEY` to your `.env` and restarting.\
"""

SYNC_CHAIN_INSTRUCTIONS = """

## Sync Chain

After any workflow that creates or modifies files in context/, **always delegate
to Syncer as the final step** to commit and push changes to GitHub. This ensures
the knowledge base is durable and available everywhere.

Chain examples:
- User ingests a URL → Researcher saves to raw/ → **Syncer pushes**
- Scheduled compile → Compiler writes wiki articles → **Syncer pushes**
- Scheduled lint → Linter writes lint report → **Syncer pushes**
- Navigator saves meeting notes or drafts a file → **Syncer pushes**
- Weekly review → Navigator writes to meetings/ → **Syncer pushes**

Do NOT skip the Syncer step. Every file change must be pushed.\
"""

SYNC_DISABLED_INSTRUCTIONS = """

## Git Sync — Not Configured

If the user asks about sync status, pushing, or pulling context, respond exactly:
> Git sync isn't set up yet. Context changes are only stored locally. Add `GITHUB_ACCESS_TOKEN` and `SCOUT_REPO_URL` to your `.env` and restart to enable git-backed persistence.

Do not delegate sync questions to Navigator.\
"""

SLACK_LEADER_INSTRUCTIONS = """

## Slack

When posting to Slack (scheduled tasks, user requests), use your SlackTools directly.\
"""

SLACK_DISABLED_LEADER_INSTRUCTIONS = """

## Slack — Not Configured

If the user asks to post to Slack, respond exactly:
> Slack isn't set up yet. Follow the setup guide in `docs/SLACK_CONNECT.md` to connect your workspace.

Do not attempt any Slack tool calls.\
"""

# Assemble instructions
instructions = LEADER_INSTRUCTIONS
if SLACK_TOKEN:
    instructions += SLACK_LEADER_INSTRUCTIONS
else:
    instructions += SLACK_DISABLED_LEADER_INSTRUCTIONS
if not researcher:
    instructions += RESEARCHER_DISABLED_INSTRUCTIONS
if GIT_SYNC_ENABLED:
    instructions += SYNC_CHAIN_INSTRUCTIONS
else:
    instructions += SYNC_DISABLED_INSTRUCTIONS

# Prefix the rendered manifest so the Leader sees ground truth on what
# sources are reachable before it routes.
instructions = build_leader_instructions(instructions)

# ---------------------------------------------------------------------------
# Members — conditional on configuration
# ---------------------------------------------------------------------------
members: list[Agent | Team] = [m for m in [navigator, researcher, compiler, linter] if m is not None]
if GIT_SYNC_ENABLED:
    members.append(syncer)

# ---------------------------------------------------------------------------
# Create Team
# ---------------------------------------------------------------------------
scout = Team(
    id="scout",
    name="Scout",
    mode=TeamMode.coordinate,
    model=OpenAIResponses(id="gpt-5.4"),
    members=members,
    db=agent_db,
    instructions=instructions,
    tools=leader_tools,
    learning=LearningMachine(
        knowledge=scout_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    add_learnings_to_context=True,
    enable_agentic_memory=True,
    search_past_sessions=True,
    num_past_sessions_to_search=10,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)

# ---------------------------------------------------------------------------
# Run Team
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        # Smoke 1: Direct response
        "Hey, what can you do?",
        # Smoke 2: Navigator — enterprise document retrieval
        "What's our PTO policy?",
        # Smoke 3: Navigator — file retrieval
        "What voice guides do we have?",
        # Smoke 4: Navigator — Gmail fallback
        "Check my latest emails",
        # Smoke 5: Researcher — ingest (requires PARALLEL_API_KEY)
        "Ingest this article: https://example.com/article-on-rag",
        # Smoke 6: Navigator — capture
        "Save a note: Met with Sarah Chen from Acme Corp about a partnership.",
        # Smoke 7: Compiler trigger
        "Compile any new sources into the wiki",
        # Smoke 8: Linter trigger
        "Run a health check on the wiki",
        # Smoke 9: Syncer — check status
        "What's the sync status?",
    ]
    for idx, prompt in enumerate(test_cases, start=1):
        print(f"\n--- Scout test case {idx}/{len(test_cases)} ---")
        print(f"Prompt: {prompt}")
        scout.print_response(prompt, stream=True)
