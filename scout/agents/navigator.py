"""
Navigator Agent
===============

The primary agent users interact with. Handles email, calendar,
SQL, files, enterprise documents, web research, and wiki-aware Q&A.

Reads the wiki index first for knowledge questions, then pulls
specific articles. Falls back to raw/ and live sources.

Navigator is the read-only specialist. Its SQLTools is bound to
``get_readonly_engine()`` so any INSERT/UPDATE/DELETE/DDL is rejected
at the PostgreSQL level. Its FileTools is read-only because Navigator
does not write compiled articles, does not hand-edit context files,
and does not delete files. Writes land with the Compiler (context/)
or Engineer (SQL).
"""

from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openai import OpenAIResponses
from agno.tools.file import FileTools
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_readonly_engine
from scout.instructions import navigator_instructions
from scout.settings import (
    CONTEXT_DIR,
    EXA_MCP_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_PROJECT_ID,
    PARALLEL_API_KEY,
    agent_db,
    scout_knowledge,
    scout_learnings,
)
from scout.tools.knowledge import create_update_knowledge
from scout.tools.manifest_tools import create_manifest_tool
from scout.tools.sources import create_source_tools


def _web_search_tools() -> list:
    """Web search backend selection.

    Parallel is the premium path (better extraction, higher rate limits)
    when PARALLEL_API_KEY is set. Otherwise we fall back to Exa's public
    MCP endpoint, which works keyless — this is what lets a freshly-cloned
    Scout with only OPENAI_API_KEY answer "tell me about X" questions.
    """
    if PARALLEL_API_KEY:
        from agno.tools.parallel import ParallelTools  # lazy — optional dep

        return [ParallelTools()]

    from agno.tools.mcp import MCPTools  # lazy — opens network on init

    return [MCPTools(url=EXA_MCP_URL)]


def _navigator_tools(knowledge: Knowledge) -> list:
    tools: list = [
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
        FileTools(
            base_dir=CONTEXT_DIR,
            enable_save_file=False,
            enable_read_file=True,
            enable_list_files=True,
            enable_search_files=True,
            enable_delete_file=False,
        ),
        create_update_knowledge(knowledge),
        create_manifest_tool("navigator"),
        *create_source_tools("navigator"),
        *_web_search_tools(),
    ]

    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_PROJECT_ID:
        # Drafts-allowed but no send: Agno's Toolkit `exclude_tools=[...]`
        # strips tool functions before they reach the model.
        from agno.tools.gmail import GmailTools  # type: ignore[import-not-found]
        from agno.tools.googlecalendar import GoogleCalendarTools  # type: ignore[import-not-found]

        tools.append(GmailTools(exclude_tools=["send_email", "send_email_reply"]))
        tools.append(
            GoogleCalendarTools(
                # allow_update=False keeps the OAuth scope read-only, so
                # even if a tool slips through it will fail at API time.
                allow_update=False,
                exclude_tools=["create_event", "update_event", "delete_event"],
            )
        )

    return tools


navigator = Agent(
    id="navigator",
    name="Navigator",
    role="Primary agent for user interaction, knowledge queries, email, calendar, SQL, enterprise documents, and wiki Q&A",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=navigator_instructions(),
    knowledge=scout_knowledge,
    search_knowledge=True,
    learning=LearningMachine(
        knowledge=scout_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=_navigator_tools(scout_knowledge),
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=10,
    markdown=True,
)
