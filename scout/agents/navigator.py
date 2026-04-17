"""
Navigator Agent
===============

The primary agent users interact with. Handles email, calendar,
SQL, files, enterprise documents, web research, and wiki-aware Q&A.

Reads the wiki index first for knowledge questions, then pulls
specific articles. Falls back to raw/ and live sources.
"""

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.anthropic import Claude

from scout.agents.settings import agent_db, scout_knowledge, scout_learnings
from scout.instructions import build_navigator_instructions
from scout.tools import build_navigator_tools

navigator = Agent(
    id="navigator",
    name="Navigator",
    role="Primary agent for user interaction, knowledge queries, email, calendar, SQL, enterprise documents, and wiki Q&A",
    model=Claude(id="claude-opus-4-7"),
    db=agent_db,
    instructions=build_navigator_instructions(),
    knowledge=scout_knowledge,
    search_knowledge=True,
    learning=LearningMachine(
        knowledge=scout_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=build_navigator_tools(scout_knowledge),
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=10,
    markdown=True,
)
