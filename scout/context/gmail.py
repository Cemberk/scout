"""GmailContext — agentic read-only context over Gmail.

Registered when ``GOOGLE_CLIENT_ID`` / ``GOOGLE_CLIENT_SECRET`` /
``GOOGLE_PROJECT_ID`` are all set. Agno's ``GmailTools`` handles the
OAuth flow on first use. We exclude the send / modify tools explicitly
— this is a read-only context.
"""

from __future__ import annotations

import logging
from os import getenv

from agno.agent import Agent
from agno.models.openai import OpenAIResponses

from scout.context.base import Answer, HealthState, HealthStatus

log = logging.getLogger(__name__)


_WRITE_TOOLS = [
    "create_draft_email",
    "send_email",
    "send_email_reply",
    "mark_email_as_read",
    "mark_email_as_unread",
    "star_email",
    "unstar_email",
    "archive_email",
    "apply_label",
    "remove_label",
]


class GmailContext:
    """Agentic context over Gmail's API. Read-only."""

    id: str = "gmail"
    name: str = "Gmail"
    kind: str = "gmail"

    def __init__(self) -> None:
        self._agent: Agent | None = None

    def health(self) -> HealthStatus:
        cid = getenv("GOOGLE_CLIENT_ID", "")
        secret = getenv("GOOGLE_CLIENT_SECRET", "")
        project = getenv("GOOGLE_PROJECT_ID", "")
        if not (cid and secret and project):
            missing = [
                n
                for n, v in (
                    ("GOOGLE_CLIENT_ID", cid),
                    ("GOOGLE_CLIENT_SECRET", secret),
                    ("GOOGLE_PROJECT_ID", project),
                )
                if not v
            ]
            return HealthStatus(HealthState.DISCONNECTED, f"missing: {missing}")
        try:
            from agno.tools.gmail import GmailTools  # type: ignore[import-not-found]

            gt = GmailTools()
            # _auth runs on first tool call; do it up front so health
            # surfaces OAuth issues honestly.
            gt._auth()  # noqa: SLF001 — the intent is a real connection probe
            service = gt._build_service()  # noqa: SLF001
            profile = service.users().getProfile(userId="me").execute()
        except Exception as exc:
            return HealthStatus(HealthState.DISCONNECTED, f"profile fetch failed: {exc}")
        email = profile.get("emailAddress", "authenticated")
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
            return Answer(text="Gmail not configured (GOOGLE_* env missing)", hits=[])
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
        from agno.tools.gmail import GmailTools  # type: ignore[import-not-found]

        tools = [GmailTools(exclude_tools=_WRITE_TOOLS)]
        return Agent(
            id="gmail-context",
            name="GmailContext",
            role="Read-only search over the user's Gmail",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=_INSTRUCTIONS,
            tools=tools,
            markdown=True,
        )


_INSTRUCTIONS = """\
You answer questions by searching Gmail. Workflow:

1. Pick the tool:
   - Free text query → `search_emails`.
   - Recent activity → `get_latest_emails` / `get_unread_emails`.
   - Per-person → `get_emails_from_user`.
   - Full thread → `get_emails_by_thread` once you have a thread id.
2. Cite the subject line + sender + date — enough for the user to find
   the thread in Gmail.
3. Summarize threads; only quote when exact wording matters.
4. If nothing matches, say so plainly.

You are read-only. Never send, draft, modify, label, or star — those
tools are not wired.
"""
