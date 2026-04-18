"""
Scout — Enterprise Context Agent
==================================

Three specialists coordinated by a Leader:

- Navigator:  reads the wiki + live sources, handles SQL, files, email,
              calendar, web search
- Researcher: gathers sources from the web, ingests to raw/ (conditional
              on PARALLEL_API_KEY)
- Compiler:   reads raw/, compiles wiki articles, runs lint checks
              (broken backlinks, stale articles, needs_split, user-edit
              conflicts) at the end of every compile pass

Sync (git push/pull for context/) is a Leader tool, not an agent —
three tools are not enough mass to justify a specialist.

Test:
    python -m scout.team
"""

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.team import Team, TeamMode

from scout.agents import compiler, navigator, researcher
from scout.agents.settings import agent_db, scout_learnings
from scout.config import SLACK_TOKEN
from scout.instructions import build_leader_instructions
from scout.tools import build_leader_tools

# ---------------------------------------------------------------------------
# Team Leader tools — Slack posting (conditional on SLACK_TOKEN)
# ---------------------------------------------------------------------------
leader_tools: list = build_leader_tools()

# ---------------------------------------------------------------------------
# Team instructions
# ---------------------------------------------------------------------------

LEADER_INSTRUCTIONS = """\
You are Scout, an enterprise knowledge agent that navigates your company's context graph.

You lead three specialists. Route every non-greeting request using the
rules below. There are no other routes.

## Routing rules

| Intent signal | Delegate to |
|---|---|
| Question answerable from `context/compiled/`, Drive, Slack, GitHub, SQL | **Navigator** |
| "Ingest this URL / PDF / page" or "add to raw" | **Researcher** |
| "Compile", "recompile X", "update the wiki", "lint the wiki", "check for broken links" | **Compiler** |

Ambiguous intent → ask Navigator first. You never read sources directly;
delegation is mandatory for any non-trivial answer.

Direct-response exceptions (no delegation, no tools): greetings, thanks,
"what can you do?", meta-questions about Scout itself. When the user
asks "what can you do?" or similar capability questions, name the
specialists explicitly — **Navigator** (knowledge/Q&A, wiki, SQL,
email, calendar) and **Compiler** (wiki builds, lint, broken links) —
so routing is transparent.

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

## Web Research — Researcher Not Configured

Navigator has `parallel_search` + `parallel_extract` via ParallelTools.
For dedicated ingest-into-raw/ workflows, set `PARALLEL_API_KEY` and
restart — the Researcher agent activates automatically.\
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

# Prefix the rendered manifest so the Leader sees ground truth on what
# sources are reachable before it routes.
instructions = build_leader_instructions(instructions)

# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
members: list[Agent | Team] = [m for m in [navigator, researcher, compiler] if m is not None]

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
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)


if __name__ == "__main__":
    test_cases = [
        "Hey, what can you do?",
        "What's our PTO policy?",
        "Check my latest emails",
        "Ingest this article: https://example.com/article-on-rag",
        "Compile any new sources into the wiki",
        "Lint the wiki — find stale articles and broken backlinks",
        "What's the sync status?",
    ]
    for idx, prompt in enumerate(test_cases, start=1):
        print(f"\n--- Scout test case {idx}/{len(test_cases)} ---")
        print(f"Prompt: {prompt}")
        scout.print_response(prompt, stream=True)
