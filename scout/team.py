"""
Scout — Enterprise Context Agent
================================

A single ``agno.Agent`` with N ``ContextProvider``s. Exposes
``query_<id>`` + ``update_<id>`` tools per registered provider, plus
``list_contexts``. One LLM hop per turn.
"""

from __future__ import annotations

from agno.agent import Agent

from scout.contexts import get_context_providers, list_contexts
from scout.instructions import SCOUT_INSTRUCTIONS
from scout.settings import agent_db, default_model


def scout_tools() -> list:
    """Build Scout's tool list from the active context providers.

    We use a callable (not a resolved list) so agno re-resolves per run —
    lets eval fixtures swap providers via ``update_context_providers`` and
    see the new tool set immediately, without Scout holding a stale closure.
    """
    tools: list = []
    for ctx in get_context_providers():
        tools.extend(ctx.get_tools())
    tools.append(list_contexts)
    return tools


scout = Agent(
    id="scout",
    name="Scout",
    role="Enterprise context agent",
    model=default_model(),
    db=agent_db,
    instructions=SCOUT_INSTRUCTIONS,
    tools=scout_tools,
    cache_callables=False,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)
