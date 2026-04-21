"""Context registry.

Owns the pair of singletons every agent's tool list depends on:
- ``_wiki``     — the one ``WikiContextProvider``
- ``_contexts`` — the list of live-read ``ContextProvider`` instances

Each provider exposes its own ``query_<id>`` tool via
``ContextProvider.get_tools()``; there is no dispatcher.

``set_runtime(wiki, contexts)`` installs the pair AND rewires Explorer
and Engineer so their per-provider tools match the new registry. One
call, one state change. The app lifespan calls it once at startup; eval
fixtures call it per case when they swap providers.

``list_contexts`` is a meta tool for answering "what's reachable?"
without asking each provider individually.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from agno.tools import tool

if TYPE_CHECKING:
    from scout.context.base import ContextProvider
    from scout.context.wiki.provider import WikiContextProvider

log = logging.getLogger(__name__)


_wiki: WikiContextProvider | None = None
_contexts: list[ContextProvider] = []


def set_runtime(wiki: WikiContextProvider | None, contexts: list[ContextProvider]) -> None:
    """Install the registry singletons and rewire agent tool lists.

    ``wiki`` may be None — agents come up with just their base tools
    until a real wiki is wired (in practice this only happens during
    module-load before the lifespan runs).
    """
    global _wiki, _contexts
    _wiki = wiki
    _contexts = list(contexts)

    # Rewire agents whose tools derive from the registry. Imports are
    # runtime-local to avoid a circular import at module load (the agent
    # modules import ``get_wiki`` / ``get_contexts`` from here).
    from scout.agents.engineer import engineer, engineer_tools
    from scout.agents.explorer import explorer, explorer_tools

    explorer.tools = explorer_tools()  # type: ignore[assignment]
    engineer.tools = engineer_tools()  # type: ignore[assignment]


def get_wiki() -> WikiContextProvider | None:
    return _wiki


def get_contexts() -> list[ContextProvider]:
    return list(_contexts)


@tool
def list_contexts() -> str:
    """List registered contexts + the wiki, with current health.

    Use this when the user asks what data sources are reachable, or
    when you need a meta view. For actually querying a source, call the
    source's ``query_<id>`` tool directly.

    Returns:
        JSON list of ``{id, name, kind, health, detail}``.
    """
    rows = []
    targets: list = []
    if _wiki is not None:
        targets.append(_wiki)
    targets.extend(_contexts)
    for target in targets:
        try:
            health = target.health()
            state = health.state.value if hasattr(health.state, "value") else str(health.state)
            detail = health.detail
        except Exception as exc:
            state = "disconnected"
            detail = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "id": target.id,
                "name": target.name,
                "kind": target.kind,
                "health": state,
                "detail": detail,
            }
        )
    return json.dumps(rows)
