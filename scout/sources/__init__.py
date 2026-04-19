"""
Source registry
===============

Central place that decides which Sources are live in this Scout instance.

The two always-present sources are:
- `local:raw`    — `context/raw/` (compile=True, live_read=False)
- `local:wiki`   — `context/compiled/` (compile=False, live_read=True)

Drive is added when `DRIVE_SOURCE_ENABLED` is true (Google integration set
up). Folder scope is managed on the Google side by sharing folders with
Scout's account — no server-side folder allowlist.

The registry is module-level cached. Call `reload_sources()` from the
manifest API to pick up env changes without restarting.
"""

from __future__ import annotations

from functools import lru_cache

from scout.settings import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    DRIVE_SOURCE_ENABLED,
    S3_BUCKETS,
    S3_SOURCE_ENABLED,
    SCOUT_COMPILED_DIR,
    SCOUT_RAW_DIR,
    SLACK_BOT_TOKEN,
    SLACK_SOURCE_ENABLED,
)
from scout.sources.base import Source
from scout.sources.drive import GoogleDriveSource
from scout.sources.local_folder import LocalFolderSource
from scout.sources.s3 import S3Source, parse_bucket_spec
from scout.sources.slack import SlackSource


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
                id="drive",
                name="Google Drive",
                compile=False,
                live_read=True,
            )
        )

    if SLACK_SOURCE_ENABLED:
        sources.append(
            SlackSource(
                token=SLACK_BOT_TOKEN,
                id="slack",
                name="Slack",
                compile=False,
                live_read=True,
            )
        )

    if S3_SOURCE_ENABLED:
        for spec in S3_BUCKETS:
            bucket, prefix = parse_bucket_spec(spec)
            if not bucket:
                continue
            sources.append(
                S3Source(
                    bucket=bucket,
                    prefix=prefix,
                    region=AWS_REGION,
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                    compile=True,
                    live_read=False,
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
    "S3Source",
    "SlackSource",
    "get_source",
    "get_sources",
    "parse_bucket_spec",
    "reload_sources",
]
