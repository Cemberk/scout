"""Shared Learnings tool — all three specialists write to scout_learnings.

One operational-memory store: routing hints, corrections, per-user
preferences. Explorer / Engineer / Doctor attach it as their
LearningMachine's knowledge base in agentic mode.
"""

from __future__ import annotations

from agno.knowledge import Knowledge
from agno.tools import tool


def create_update_learnings(knowledge: Knowledge):
    """Bind an update_learnings tool to a shared Knowledge instance.

    Args:
        knowledge: The ``scout_learnings`` PgVector knowledge base.

    Returns:
        A tool callable for Explorer / Engineer / Doctor.
    """

    @tool
    def update_learnings(note: str, title: str | None = None) -> str:
        """Save an operational-memory note to scout_learnings.

        Use this for things Scout should remember across sessions:
        - Routing hints ("handbook stuff lives in wiki", "infra stuff in slack")
        - Corrections ("user prefers short answers")
        - Per-user preferences, recurring patterns, known gotchas

        Args:
            note: The learning content.
            title: Optional title — defaults to the first 80 chars of the note.

        Returns:
            Confirmation message.
        """
        display = title or note.strip().splitlines()[0][:80] or "learning"
        knowledge.insert(name=display, text_content=note)
        return f"Learning saved: {display}"

    return update_learnings
