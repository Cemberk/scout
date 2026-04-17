"""
GoogleDriveSource
=================

Live-read source backed by the Google Drive v3 API.

Per spec §3.1.5: Drive in Phase 1 is `compile=False, live_read=True`.
Drive's own search is excellent — compiling creates a drifting mirror users
can't edit back into Drive. Users who want Obsidian copies can flip the
flag manually.

Auth: per-user OAuth, reusing the credentials produced by Agno's existing
Google integration. We rely on `agno.tools.google.calendar` /
`agno.tools.google.gmail` to have stamped a refreshable token on disk; we
just borrow it. If Google integration isn't configured the source is
unhealthy and the manifest hides it.

Capabilities: LIST, READ, METADATA, FIND_NATIVE.
"""

from __future__ import annotations

import io
import mimetypes
from pathlib import Path
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

# Google's "export as plain text" mime types for Workspace files
_GOOGLE_EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/markdown",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


class GoogleDriveSource:
    """Live-read Google Drive, scoped to a configured set of folder IDs.

    Lazy: the Drive client is built on first call, not at __init__ time.
    Health checks are cheap — `about.get` if a client exists, otherwise an
    UNCONFIGURED status.
    """

    def __init__(
        self,
        folder_ids: Iterable[str],
        *,
        id: str = "drive",
        name: str = "Google Drive",
        compile: bool = False,
        live_read: bool = True,
    ) -> None:
        self.folder_ids = tuple(folder_ids)
        self.id = id
        self.name = name
        self.compile = compile
        self.live_read = live_read
        self._service = None  # type: ignore[var-annotated]

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    def _service_or_none(self):
        if self._service is not None:
            return self._service
        try:
            from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
            from googleapiclient.discovery import build  # type: ignore[import-not-found]
        except ImportError:
            return None

        token_path = self._token_path()
        if not token_path or not token_path.exists():
            return None
        try:
            creds = Credentials.from_authorized_user_file(str(token_path))
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
            return self._service
        except Exception:
            return None

    def _token_path(self) -> Path | None:
        """Find the OAuth token agno's Google tools persist."""
        for candidate in (
            Path.home() / ".agno" / "google" / "token.json",
            Path.home() / ".credentials" / "token.json",
            Path("token.json"),
        ):
            if candidate.exists():
                return candidate
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _q_in_scope(self) -> str:
        if not self.folder_ids:
            return "trashed = false"
        parents = " or ".join(f"'{fid}' in parents" for fid in self.folder_ids)
        return f"({parents}) and trashed = false"

    def _entry_from_file(self, f: dict) -> Entry:
        return Entry(
            id=f["id"],
            name=f.get("name", f["id"]),
            kind="folder" if f.get("mimeType") == "application/vnd.google-apps.folder" else "file",
            path=f.get("name"),
            size=int(f["size"]) if f.get("size") else None,
            modified_at=f.get("modifiedTime"),
        )

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def list(self, path: str = "") -> _list[Entry]:
        svc = self._service_or_none()
        if svc is None:
            raise SourceError("Drive client not configured (no token)")
        # `path` is treated as a folder id override if provided.
        if path:
            q = f"'{path}' in parents and trashed = false"
        else:
            q = self._q_in_scope()
        out: list[Entry] = []
        page_token = None
        while True:
            resp = (
                svc.files()
                .list(
                    q=q,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)",
                    pageSize=200,
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                )
                .execute()
            )
            for f in resp.get("files", []):
                out.append(self._entry_from_file(f))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def read(self, entry_id: str) -> Content:
        svc = self._service_or_none()
        if svc is None:
            raise SourceError("Drive client not configured (no token)")
        meta = (
            svc.files()
            .get(fileId=entry_id, fields="id, name, mimeType, webViewLink, size", supportsAllDrives=True)
            .execute()
        )
        mime = meta.get("mimeType", "application/octet-stream")
        export_mime = _GOOGLE_EXPORT_MIME.get(mime)

        if export_mime:
            request = svc.files().export_media(fileId=entry_id, mimeType=export_mime)
            data = self._download(request)
            text = data.decode("utf-8", errors="replace")
            return Content(
                bytes=data,
                text=text,
                mime=export_mime,
                source_url=meta.get("webViewLink"),
                citation_hint=meta.get("name"),
            )

        request = svc.files().get_media(fileId=entry_id, supportsAllDrives=True)
        data = self._download(request)
        # Try to decode common text/* mimes as text
        decoded: str | None = None
        if mime.startswith("text/") or mime in {"application/json", "application/xml"}:
            decoded = data.decode("utf-8", errors="replace")
        return Content(
            bytes=data,
            text=decoded,
            mime=mime,
            source_url=meta.get("webViewLink"),
            citation_hint=meta.get("name"),
        )

    def _download(self, request) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import-not-found]

        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    def metadata(self, entry_id: str) -> Meta:
        svc = self._service_or_none()
        if svc is None:
            raise SourceError("Drive client not configured (no token)")
        meta = (
            svc.files()
            .get(
                fileId=entry_id,
                fields="id, name, mimeType, size, modifiedTime, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        return Meta(
            name=meta.get("name", entry_id),
            mime=meta.get("mimeType") or mimetypes.guess_type(meta.get("name", ""))[0],
            size=int(meta["size"]) if meta.get("size") else None,
            modified_at=meta.get("modifiedTime"),
            source_url=meta.get("webViewLink"),
            extra={"id": entry_id},
        )

    def health(self) -> HealthStatus:
        svc = self._service_or_none()
        if svc is None:
            return HealthStatus(HealthState.UNCONFIGURED, "Google OAuth token not found")
        try:
            svc.about().get(fields="user(emailAddress)").execute()
        except Exception as e:  # network / auth / quota
            return HealthStatus(HealthState.DEGRADED, str(e)[:160])
        scope = f"{len(self.folder_ids)} folder(s)" if self.folder_ids else "all accessible files"
        return HealthStatus(HealthState.CONNECTED, scope)

    def capabilities(self) -> set[Capability]:
        return {Capability.LIST, Capability.READ, Capability.METADATA, Capability.FIND_NATIVE}

    def find(self, query: str, kind: FindKind = FindKind.LEXICAL) -> _list[Hit]:
        if kind not in (FindKind.LEXICAL, FindKind.NATIVE):
            raise NotSupported(f"GoogleDriveSource does not support {kind}")
        svc = self._service_or_none()
        if svc is None:
            raise SourceError("Drive client not configured (no token)")
        # Drive's q DSL: fullText for body, name for filename
        escaped = query.replace("'", r"\'")
        scope = self._q_in_scope()
        q = f"({scope}) and (fullText contains '{escaped}' or name contains '{escaped}')"
        resp = (
            svc.files()
            .list(
                q=q,
                fields="files(id, name, mimeType, modifiedTime, webViewLink)",
                pageSize=25,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        hits: list[Hit] = []
        for f in resp.get("files", []):
            hits.append(
                Hit(
                    entry_id=f["id"],
                    name=f.get("name", f["id"]),
                    score=1.0,
                    snippet=None,  # Drive doesn't return snippets
                    source_url=f.get("webViewLink"),
                    citation_hint=f.get("name"),
                )
            )
        return hits
