"""SlackContext — agentic read-only context over Slack's API.

Registered when ``SLACK_BOT_TOKEN`` is set. Health check hits Slack's
``auth.test``. The internal agent wraps Agno's ``SlackTools`` with only
the read-capable functions enabled (no send, no upload, no download).
"""

from __future__ import annotations

import logging
from os import getenv

from agno.agent import Agent
from agno.models.openai import OpenAIResponses

from scout.context.base import Answer, HealthState, HealthStatus

log = logging.getLogger(__name__)


class SlackContext:
    """Agentic context over Slack's API."""

    id: str = "slack"
    name: str = "Slack"
    kind: str = "slack"

    def __init__(self) -> None:
        self._agent: Agent | None = None

    def health(self) -> HealthStatus:
        token = getenv("SLACK_BOT_TOKEN", "")
        if not token:
            return HealthStatus(HealthState.DISCONNECTED, "SLACK_BOT_TOKEN not set")
        try:
            from slack_sdk import WebClient  # type: ignore[import-not-found]

            client = WebClient(token=token)
            resp = client.auth_test()
        except Exception as exc:
            return HealthStatus(HealthState.DISCONNECTED, f"auth.test failed: {exc}")
        if not resp.get("ok"):
            return HealthStatus(HealthState.DISCONNECTED, resp.get("error") or "auth.test returned ok=false")
        team = resp.get("team") or "workspace"
        user = resp.get("user") or "bot"
        return HealthStatus(HealthState.CONNECTED, f"{user}@{team}")

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
            return Answer(text="Slack not configured (SLACK_BOT_TOKEN missing)", hits=[])
        output = agent.run(question)
        text = output.get_content_as_string() if hasattr(output, "get_content_as_string") else str(output.content)
        return Answer(text=text or "", hits=[])

    def _ensure_agent(self) -> Agent | None:
        if self._agent is not None:
            return self._agent
        token = getenv("SLACK_BOT_TOKEN", "")
        if not token:
            return None
        self._agent = self._build_agent(token)
        return self._agent

    def _build_agent(self, token: str) -> Agent:
        from agno.tools.slack import SlackTools

        tools = [
            SlackTools(
                token=token,
                enable_send_message=False,
                enable_send_message_thread=False,
                enable_list_channels=True,
                enable_get_channel_history=True,
                enable_search_workspace=True,
                enable_search_messages=True,
                enable_get_thread=True,
                enable_list_users=True,
                enable_get_user_info=True,
                enable_get_channel_info=True,
                enable_upload_file=False,
                enable_download_file=False,
            )
        ]
        return Agent(
            id="slack-context",
            name="SlackContext",
            role="Read-only exploration of the Slack workspace",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=_INSTRUCTIONS,
            tools=tools,
            markdown=True,
        )


_INSTRUCTIONS = """\
You answer questions by searching Slack. Workflow:

1. Pick the best surface:
   - Free text query → `search_workspace` (modern) or `search_messages` (legacy fallback).
   - Known channel → `list_channels` + `get_channel_history`.
   - Known thread → `get_thread`.
   - Person → `list_users` / `get_user_info`.
2. Cite `#channel / @user / <thread-ts>` in the answer — links back to
   the conversation.
3. Summarize threads and multi-message results; only quote when the
   exact wording matters.
4. If nothing matches, say so plainly with what you searched.

You are read-only. Never send messages or upload files — the tools for
those are not wired.
"""
