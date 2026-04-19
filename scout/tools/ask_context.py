"""Explorer's tools: ask_context + list_contexts.

Both tools read from module-level singletons populated at startup by
``scout.context.config.build_wiki`` + ``build_contexts``. Set them via
``set_runtime(wiki, contexts)`` from ``app/main.py`` lifespan.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from agno.tools import tool

if TYPE_CHECKING:
    from scout.context.base import Context
    from scout.context.wiki import WikiContext

log = logging.getLogger(__name__)


_wiki: WikiContext | None = None
_contexts: list[Context] = []


def set_runtime(wiki: WikiContext, contexts: list[Context]) -> None:
    """Install the singletons. Called once from the app lifespan."""
    global _wiki, _contexts
    _wiki = wiki
    _contexts = list(contexts)


def get_wiki() -> WikiContext | None:
    return _wiki


def get_contexts() -> list[Context]:
    return list(_contexts)


def _targets() -> dict[str, Context | WikiContext]:
    targets: dict[str, Context | WikiContext] = {}
    if _wiki is not None:
        targets["wiki"] = _wiki
    for ctx in _contexts:
        targets[ctx.id] = ctx
    return targets


@tool
def ask_context(context_id: str, question: str, limit: int = 10) -> str:
    """Ask a registered context or the wiki. ``context_id='wiki'`` targets the wiki.

    Args:
        context_id: One of the ids returned by ``list_contexts()``, or ``'wiki'``.
        question: Natural-language question.
        limit: Soft cap on internal retrieval breadth (context-specific).

    Returns:
        JSON string ``{"answer": ..., "hits": [...]}`` or ``{"error": ...}``.
    """
    targets = _targets()
    target = targets.get(context_id)
    if target is None:
        return json.dumps(
            {
                "error": f"unknown context {context_id!r}",
                "available": sorted(targets.keys()),
            }
        )
    try:
        answer = target.query(question, limit=limit)
    except Exception as exc:
        log.exception("ask_context: %s failed", context_id)
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    return json.dumps(
        {
            "answer": answer.text,
            "hits": [h.__dict__ for h in answer.hits],
        }
    )


@tool
def list_contexts() -> str:
    """List registered contexts + the wiki, with current health.

    Returns:
        JSON list of ``{id, name, kind, health, detail}``.
    """
    rows = []
    for ctx_id, target in _targets().items():
        try:
            health = target.health()
            state = health.state.value if hasattr(health.state, "value") else str(health.state)
            detail = health.detail
        except Exception as exc:
            state = "disconnected"
            detail = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "id": ctx_id,
                "name": target.name,
                "kind": target.kind,
                "health": state,
                "detail": detail,
            }
        )
    return json.dumps(rows)
