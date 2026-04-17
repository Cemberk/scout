"""
Source registry
===============

Central place that decides which Sources are live in this Scout instance.

The two always-present sources are:
- `local:raw`    — `context/raw/` (compile=True, live_read=False)
- `local:wiki`   — `context/compiled/` (compile=False, live_read=True)

Drive is added when `DRIVE_SOURCE_ENABLED` is true (Google integration set
up + at least one folder ID configured).

The registry is module-level cached. Call `reload_sources()` from the
manifest API to pick up env changes without restarting.
"""

from __future__ import annotations

from functools import lru_cache

from scout.config import (
    DRIVE_SOURCE_ENABLED,
    GOOGLE_DRIVE_FOLDER_IDS,
    SCOUT_COMPILED_DIR,
    SCOUT_RAW_DIR,
)
from scout.sources.base import Source
from scout.sources.drive import GoogleDriveSource
from scout.sources.local_folder import LocalFolderSource


@lru_cache(maxsize=1)
def get_sources() -> tuple[Source, ...]:
    SCOUT_RAW_DIR.mkdir(parents=True, exist_ok=True)
    SCOUT_COMPILED_DIR.mkdir(parents=True, exist_ok=True)

    sources: list[Source] = [
        LocalFolderSource(
            SCOUT_RAW_DIR,
            id="local:raw",
            name="Raw Intake",
            compile=True,
            live_read=False,
        ),
        LocalFolderSource(
            SCOUT_COMPILED_DIR,
            id="local:wiki",
            name="Compiled Wiki",
            compile=False,
            live_read=True,
        ),
    ]

    if DRIVE_SOURCE_ENABLED:
        sources.append(
            GoogleDriveSource(
                folder_ids=GOOGLE_DRIVE_FOLDER_IDS,
                id="drive",
                name="Google Drive",
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
    "get_source",
    "get_sources",
    "reload_sources",
]
