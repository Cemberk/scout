"""Scout — Enterprise context agent.

The `scout` attribute (Team) is imported lazily so that entry points which
only need manifest / tool-gating surface (e.g. `python -m scout _smoke_gating`)
don't drag in optional dependencies (Parallel, Slack, Google) transitively.
"""

from __future__ import annotations

__all__ = ["scout"]


def __getattr__(name: str):
    if name == "scout":
        from scout.team import scout as _scout

        return _scout
    raise AttributeError(f"module 'scout' has no attribute {name!r}")
