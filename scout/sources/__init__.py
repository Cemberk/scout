"""
Source registry
===============

Central place that decides which Sources are live in this Scout instance.

The two always-present sources are:
- `local:raw`    — `context/raw/` (compile=True, live_read=False)
- `local:wiki`   — `context/compiled/` (compile=False, live_read=True)

Drive is added when the Google integration is configured. Folder scope is
managed on the Google side by sharing folders with Scout's account — no
server-side folder allowlist.

The registry is module-level cached. Call `reload_sources()` from the
manifest API to pick up env changes without restarting.
"""

from __future__ import annotations

from functools import lru_cache

from scout.settings import (
    CONTEXT_COMPILED_DIR,
    CONTEXT_RAW_DIR,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_PROJECT_ID,
    SLACK_BOT_TOKEN,
)
from scout.sources.base import Source
from scout.sources.drive import GoogleDriveSource
from scout.sources.local_folder import LocalFolderSource
from scout.sources.slack import SlackSource


@lru_cache(maxsize=1)
def get_sources() -> tuple[Source, ...]:
    CONTEXT_RAW_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_COMPILED_DIR.mkdir(parents=True, exist_ok=True)

    sources: list[Source] = [
        LocalFolderSource(
            CONTEXT_RAW_DIR,
            id="local:raw",
            name="Raw Intake",
            compile=True,
            live_read=False,
        ),
        LocalFolderSource(
            CONTEXT_COMPILED_DIR,
            id="local:wiki",
            name="Compiled Wiki",
            compile=False,
            live_read=True,
        ),
    ]

    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_PROJECT_ID:
        sources.append(
            GoogleDriveSource(
                id="drive",
                name="Google Drive",
                compile=False,
                live_read=True,
            )
        )

    if SLACK_BOT_TOKEN:
        sources.append(
            SlackSource(
                token=SLACK_BOT_TOKEN,
                id="slack",
                name="Slack",
                compile=False,
                live_read=True,
            )
        )

    return tuple(sources)


def reload_sources() -> tuple[Source, ...]:
    get_sources.cache_clear()
    return get_sources()


def get_source(source_id: str) -> Source | None:
    for s in get_sources():
        if s.id == source_id:
            return s
    return None


__all__ = [
    "GoogleDriveSource",
    "LocalFolderSource",
    "SlackSource",
    "get_source",
    "get_sources",
    "reload_sources",
]
