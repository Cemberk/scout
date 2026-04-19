"""Scout context + wiki layer.

Public surface:
    - Context / HealthState / HealthStatus / Answer / Hit / Entry / WikiBackend
      from scout.context.base
    - WikiContext from scout.context.wiki (added in 1f)
    - build_wiki / build_contexts / parse_spec from scout.context.config (added in 1b)
"""

from scout.context.base import (
    Answer,
    Context,
    Entry,
    HealthState,
    HealthStatus,
    Hit,
    WikiBackend,
)

__all__ = [
    "Answer",
    "Context",
    "Entry",
    "HealthState",
    "HealthStatus",
    "Hit",
    "WikiBackend",
]
