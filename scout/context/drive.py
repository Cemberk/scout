"""DriveContext — agentic read-only context over Google Drive.

Registered when ``GOOGLE_CLIENT_ID`` / ``GOOGLE_CLIENT_SECRET`` /
``GOOGLE_PROJECT_ID`` are all set. Shares the same OAuth app as
GmailContext.

Drive access is scoped on the Google side by sharing folders with the
Scout bot account — this code does not filter further.
"""

from __future__ import annotations

import logging
from os import getenv

from agno.agent import Agent
from agno.models.openai import OpenAIResponses

from scout.context.base import Answer, HealthState, HealthStatus

log = logging.getLogger(__name__)


_WRITE_TOOLS = [
    "upload_file",
    "aupload_file",
]


class DriveContext:
    """Agentic context over Google Drive. Read-only."""

    id: str = "drive"
    name: str = "Drive"
    kind: str = "drive"

    def __init__(self) -> None:
        self._agent: Agent | None = None

    def health(self) -> HealthStatus:
        cid = getenv("GOOGLE_CLIENT_ID", "")
        secret = getenv("GOOGLE_CLIENT_SECRET", "")
        project = getenv("GOOGLE_PROJECT_ID", "")
        if not (cid and secret and project):
            missing = [n for n, v in (("GOOGLE_CLIENT_ID", cid), ("GOOGLE_CLIENT_SECRET", secret), ("GOOGLE_PROJECT_ID", project)) if not v]
            return HealthStatus(HealthState.DISCONNECTED, f"missing: {missing}")
        try:
            from agno.tools.google.drive import GoogleDriveTools  # type: ignore[import-not-found]

            gdt = GoogleDriveTools()
            gdt._auth()  # noqa: SLF001
            service = gdt._build_service()  # noqa: SLF001
            about = service.about().get(fields="user(emailAddress)").execute()
        except Exception as exc:
            return HealthStatus(HealthState.DISCONNECTED, f"about fetch failed: {exc}")
        email = (about.get("user") or {}).get("emailAddress", "authenticated")
        return HealthStatus(HealthState.CONNECTED, email)

    def query(
        self,
        question: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> Answer:
        del filters, limit
        agent = self._ensure_agent()
        if agent is None:
            return Answer(text="Drive not configured (GOOGLE_* env missing)", hits=[])
        output = agent.run(question)
        text = output.get_content_as_string() if hasattr(output, "get_content_as_string") else str(output.content)
        return Answer(text=text or "", hits=[])

    def _ensure_agent(self) -> Agent | None:
        if self._agent is not None:
            return self._agent
        if not (getenv("GOOGLE_CLIENT_ID") and getenv("GOOGLE_CLIENT_SECRET") and getenv("GOOGLE_PROJECT_ID")):
            return None
        self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        from agno.tools.google.drive import GoogleDriveTools  # type: ignore[import-not-found]

        tools = [GoogleDriveTools(exclude_tools=_WRITE_TOOLS)]
        return Agent(
            id="drive-context",
            name="DriveContext",
            role="Read-only search over the user's Google Drive",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=_INSTRUCTIONS,
            tools=tools,
            markdown=True,
        )


_INSTRUCTIONS = """\
You answer questions by searching Google Drive. Workflow:

1. Pick the tool:
   - Find candidates → `search_files` (supports Drive query strings).
   - Browse a folder → `list_files`.
   - Extract content → `read_file` (handles Docs / Sheets / Slides).
   - Raw bytes → `download_file` (and export_format for native docs).
2. Cite the file title + id so the user can open it directly.
3. Summarize long docs; quote short passages verbatim when the user
   asks for policy/contract wording.
4. If nothing matches, say so plainly.

You are read-only. Do not upload — the upload tool is not wired.
"""
