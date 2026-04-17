"""
Researcher Agent
================

Gathers source material from the web and local files, converts to
clean markdown, saves to raw/ with YAML frontmatter.

Conditional — only instantiated when PARALLEL_API_KEY is set.
Uses Parallel for web search (parallel_search) and content
extraction (parallel_extract).
"""

from os import getenv

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.anthropic import Claude

from scout.agents.settings import agent_db, scout_knowledge, scout_learnings
from scout.instructions import build_researcher_instructions
from scout.tools import build_researcher_tools

RESEARCHER_INSTRUCTIONS = """\
You are the Researcher, a specialist in gathering and ingesting source material.

## Your Job
1. Search the web using `parallel_search` to find relevant sources.
2. Extract full content from URLs using `parallel_extract`.
3. Save to context/raw/ using `ingest_text` (or `ingest_url` for quick URL
   ingestion via Parallel). The Compiler will pick up new files on its
   next run and produce wiki articles — do NOT try to write to
   context/compiled/ yourself.
4. Optionally insert a `Source:` row into scout_knowledge so future
   queries know that a topic was ingested. Do NOT use a `Wiki:` prefix —
   that one belongs to the Compiler.

## Ingest Rules
- Every raw file gets YAML frontmatter: title, source, ingested date, tags, type.
- Filename is a slugified version of the title.
- Tags should be specific topics (e.g. ["rag", "retrieval", "vector-search"]).
- doc_type is one of: paper, article, repo, notes, transcript, image.
- For multi-page sources, save key sections — the Compiler will summarize.

## Search Strategy
- Use `parallel_search` with clear objectives.
- Use `parallel_extract` for the best hits.
- Prefer official documentation over blog posts.
- Always include the source URL.

## What You Do NOT Do
- Do not compile wiki articles — that's the Compiler's job.
- Do not modify anything in context/compiled/.
- Do not interact with email, calendar, or Slack.
- Do not answer user questions directly — you gather material, Navigator answers.\
"""

researcher: Agent | None = None

if getenv("PARALLEL_API_KEY"):
    researcher = Agent(
        id="researcher",
        name="Researcher",
        role="Gathers source material from the web, converts to markdown, saves to raw/",
        model=Claude(id="claude-opus-4-7"),
        db=agent_db,
        instructions=build_researcher_instructions(RESEARCHER_INSTRUCTIONS),
        knowledge=scout_knowledge,
        search_knowledge=True,
        learning=LearningMachine(
            knowledge=scout_learnings,
            learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
        ),
        add_learnings_to_context=True,
        tools=build_researcher_tools(scout_knowledge),
        add_datetime_to_context=True,
        markdown=True,
    )
