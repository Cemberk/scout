"""
SlackSource
===========

Live-read source over Slack. Per spec §4.3:
- `list(path="")` returns channels scoped to `SLACK_CHANNEL_ALLOWLIST`
  (or the bot's visible channels if the allowlist is empty).
- `list(path="<channel_id>")` returns recent message headers.
- `read("<channel>:<ts>")` returns the full thread via
  `conversations.replies`, with citation = `slack://<channel>/<ts>` and
  source_url = the message permalink.
- `find(kind=NATIVE)` uses `search.messages` scoped to allowlisted
  channels. Returns top 20.
- `health` = `auth.test`. `UNCONFIGURED` without `SLACK_TOKEN`.
- Read-only: no send tools. Posting is the Leader's job via agno's
  SlackTools, not this source.
- capabilities: LIST, READ, METADATA, FIND_NATIVE.
"""

from __future__ import annotations

from typing import Iterable

from scout.sources.base import (
    Capability,
    Content,
    Entry,
    FindKind,
    HealthState,
    HealthStatus,
    Hit,
    Meta,
    NotSupported,
    SourceError,
)

# Alias builtins.list — the class body below defines `def list`, which shadows
# `list` in class scope and breaks mypy on `-> list[...]` return annotations.
_list = list

# Keep recent-message surfacing cheap — Slack API is rate-limited.
_CHANNEL_HISTORY_LIMIT = 25
_SEARCH_HIT_LIMIT = 20


class SlackSource:
    """Live-read Slack, scoped to a channel allowlist."""

    def __init__(
        self,
        token: str,
        *,
        channel_allowlist: Iterable[str] = (),
        id: str = "slack",
        name: str = "Slack",
        compile: bool = False,
        live_read: bool = True,
    ) -> None:
        self.token = token
        self.channel_allowlist = tuple(channel_allowlist)
        self.id = id
        self.name = name
        self.compile = compile
        self.live_read = live_read
        # WebClient, populated lazily. Typed loosely to allow deferred import.
        self._client: object | None = None

    # ------------------------------------------------------------------
    # Client lifecycle — no network I/O at __init__.
    # ------------------------------------------------------------------

    def _client_or_none(self):
        if self._client is not None:
            return self._client
        if not self.token:
            return None
        try:
            from slack_sdk import WebClient  # type: ignore[import-not-found]
        except ImportError:
            return None
        self._client = WebClient(token=self.token)
        return self._client

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _allowed_channels(self) -> tuple[str, ...]:
        return self.channel_allowlist

    def _is_allowed(self, channel_id: str) -> bool:
        if not self.channel_allowlist:
            return True
        return channel_id in self.channel_allowlist

    def _permalink(self, client, channel: str, ts: str) -> str | None:
        try:
            resp = client.chat_getPermalink(channel=channel, message_ts=ts)
            return resp.get("permalink")
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def list(self, path: str = "") -> _list[Entry]:
        client = self._client_or_none()
        if client is None:
            raise SourceError("Slack client not configured")

        if path:
            # `path` is treated as a channel id. Return recent messages.
            if not self._is_allowed(path):
                raise SourceError(f"channel {path} not in allowlist")
            resp = client.conversations_history(channel=path, limit=_CHANNEL_HISTORY_LIMIT)
            return [
                Entry(
                    id=f"{path}:{m['ts']}",
                    name=(m.get("text") or "")[:80] or m["ts"],
                    kind="message",
                    path=path,
                    modified_at=m.get("ts"),
                )
                for m in resp.get("messages", [])
            ]

        # No path → channel list. Prefer the allowlist literally.
        allowed = self._allowed_channels()
        if allowed:
            entries: list[Entry] = []
            for ch in allowed:
                try:
                    info = client.conversations_info(channel=ch).get("channel") or {}
                except Exception:
                    continue
                entries.append(
                    Entry(
                        id=info.get("id", ch),
                        name=info.get("name", ch),
                        kind="channel",
                    )
                )
            return entries

        resp = client.conversations_list(types="public_channel,private_channel", exclude_archived=True, limit=200)
        return [Entry(id=c["id"], name=c["name"], kind="channel") for c in resp.get("channels", [])]

    def read(self, entry_id: str) -> Content:
        client = self._client_or_none()
        if client is None:
            raise SourceError("Slack client not configured")
        if ":" not in entry_id:
            raise SourceError(f"entry_id must be '<channel>:<ts>', got {entry_id!r}")
        channel, ts = entry_id.split(":", 1)
        if not self._is_allowed(channel):
            raise SourceError(f"channel {channel} not in allowlist")
        resp = client.conversations_replies(channel=channel, ts=ts, limit=200)
        msgs = resp.get("messages", [])
        body = "\n\n".join(f"[{m.get('user', '?')} {m.get('ts', '')}] {m.get('text', '')}" for m in msgs)
        permalink = self._permalink(client, channel, ts)
        return Content(
            text=body,
            mime="text/plain",
            source_url=permalink,
            citation_hint=f"slack://{channel}/{ts}",
        )

    def metadata(self, entry_id: str) -> Meta:
        client = self._client_or_none()
        if client is None:
            raise SourceError("Slack client not configured")
        if ":" not in entry_id:
            raise SourceError(f"entry_id must be '<channel>:<ts>', got {entry_id!r}")
        channel, ts = entry_id.split(":", 1)
        if not self._is_allowed(channel):
            raise SourceError(f"channel {channel} not in allowlist")
        permalink = self._permalink(client, channel, ts)
        return Meta(
            name=f"Slack message {ts}",
            mime="text/plain",
            source_url=permalink,
            extra={"channel": channel, "ts": ts},
        )

    def health(self) -> HealthStatus:
        if not self.token:
            return HealthStatus(HealthState.UNCONFIGURED, "SLACK_TOKEN not set")
        client = self._client_or_none()
        if client is None:
            return HealthStatus(HealthState.UNCONFIGURED, "slack_sdk not installed")
        try:
            resp = client.auth_test()
        except Exception as e:
            return HealthStatus(HealthState.DEGRADED, str(e)[:160])
        scope = (
            f"{len(self.channel_allowlist)} channel(s) allowlisted"
            if self.channel_allowlist
            else "all visible channels"
        )
        return HealthStatus(HealthState.CONNECTED, f"{resp.get('team', '?')}: {scope}")

    def capabilities(self) -> set[Capability]:
        return {Capability.LIST, Capability.READ, Capability.METADATA, Capability.FIND_NATIVE}

    def find(self, query: str, kind: FindKind = FindKind.LEXICAL) -> _list[Hit]:
        if kind not in (FindKind.LEXICAL, FindKind.NATIVE):
            raise NotSupported(f"SlackSource does not support {kind}")
        client = self._client_or_none()
        if client is None:
            raise SourceError("Slack client not configured")
        # Scope the query to allowlisted channels using Slack's `in:<name>`
        # operator. We stay permissive if we can't resolve the names.
        scoped = query
        if self.channel_allowlist:
            try:
                names = []
                for ch in self.channel_allowlist:
                    info = client.conversations_info(channel=ch).get("channel") or {}
                    if info.get("name"):
                        names.append(f"in:#{info['name']}")
                if names:
                    scoped = f"{query} ({' OR '.join(names)})"
            except Exception:
                pass  # fall back to unscoped search rather than fail
        try:
            resp = client.search_messages(query=scoped, count=_SEARCH_HIT_LIMIT)
        except Exception as e:
            raise SourceError(f"slack search failed: {e}") from e
        matches = ((resp.get("messages") or {}).get("matches") or [])[:_SEARCH_HIT_LIMIT]
        hits: list[Hit] = []
        for m in matches:
            ch_id = (m.get("channel") or {}).get("id", "")
            ts = m.get("ts", "")
            hits.append(
                Hit(
                    entry_id=f"{ch_id}:{ts}",
                    name=(m.get("text") or "")[:80] or ts,
                    score=1.0,
                    snippet=(m.get("text") or "")[:240],
                    source_url=m.get("permalink"),
                    citation_hint=f"slack://{ch_id}/{ts}",
                )
            )
        return hits
