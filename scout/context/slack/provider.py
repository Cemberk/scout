"""
Slack Context Provider
======================

Read-only Slack access for the calling agent — search the workspace,
read channels, expand threads, resolve users. Sends are explicitly
disabled; posting to Slack happens through the Slack *interface*
(see `app/main.py`), not this context.

Uses `SLACK_BOT_TOKEN` (Scout convention). If the user has only
`SLACK_TOKEN` set (agno's default), we fall back to that.
"""

from __future__ import annotations

from os import getenv
from typing import TYPE_CHECKING

from agno.agent import Agent
from agno.tools.slack import SlackTools

from scout.context._utils import answer_from_run
from scout.context.mode import ContextMode
from scout.context.provider import Answer, ContextProvider, Status

if TYPE_CHECKING:
    from agno.models.base import Model


class SlackContextProvider(ContextProvider):
    """Read-only Slack workspace access."""

    def __init__(
        self,
        *,
        token: str | None = None,
        id: str = "slack",
        name: str = "Slack",
        mode: ContextMode = ContextMode.default,
        model: Model | None = None,
    ) -> None:
        super().__init__(id=id, name=name, mode=mode, model=model)
        self.token = token or getenv("SLACK_BOT_TOKEN") or getenv("SLACK_TOKEN")
        if not self.token:
            raise ValueError("SlackContextProvider: SLACK_BOT_TOKEN (or SLACK_TOKEN) is required")
        self._tools: SlackTools | None = None
        self._agent: Agent | None = None

    def status(self) -> Status:
        if not self.token:
            return Status(ok=False, detail="SLACK_BOT_TOKEN not set")
        return Status(ok=True, detail="slack (token configured)")

    async def astatus(self) -> Status:
        return self.status()

    def query(self, question: str) -> Answer:
        return answer_from_run(self._ensure_agent().run(question))

    async def aquery(self, question: str) -> Answer:
        return answer_from_run(await self._ensure_agent().arun(question))

    def instructions(self) -> str:
        if self.mode == ContextMode.agent:
            return f"`{self.name}`: call `{self.query_tool_name}(question)` to search Slack."
        return (
            f"`{self.name}`: `search_workspace` for topic/catch-up queries across the workspace; "
            "`get_channel_history` for latest messages in a known channel; `get_thread(channel_id, ts)` "
            "to expand a thread; `get_channel_info` / `get_user_info` to resolve names. Read-only."
        )

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    def _default_tools(self) -> list:
        return self._all_tools()

    def _all_tools(self) -> list:
        return [self._ensure_tools()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_tools(self) -> SlackTools:
        if self._tools is None:
            self._tools = SlackTools(
                token=self.token,
                enable_send_message=False,
                enable_send_message_thread=False,
                enable_upload_file=False,
                enable_download_file=False,
                enable_list_channels=True,
                enable_get_channel_history=True,
                enable_search_workspace=True,
                enable_get_thread=True,
                enable_list_users=True,
                enable_get_user_info=True,
                enable_get_channel_info=True,
            )
        return self._tools

    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        return Agent(
            id=self.id,
            name=self.name,
            role="Answer questions by searching and reading Slack",
            model=self.model,
            tools=[self._ensure_tools()],
            markdown=True,
        )
