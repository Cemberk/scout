"""
MCP Context Provider
====================

Wraps a single Model Context Protocol server as a Scout context.
Supports stdio (pass `command`) and HTTP (pass `url` + optional
`transport`) transports. The escape hatch — any MCP server becomes a
registered context without writing a new provider class.

Configured via a YAML file at `SCOUT_MCP_CONFIG`. Each entry becomes
one registered provider. See [docs/MCP.md](../../../docs/MCP.md) for
the schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agno.agent import Agent
from agno.tools.mcp import MCPTools

from scout.context._utils import answer_from_run
from scout.context.mode import ContextMode
from scout.context.provider import Answer, ContextProvider, Status

if TYPE_CHECKING:
    from agno.models.base import Model


class MCPContextProvider(ContextProvider):
    """Wraps a single MCP server as a context source."""

    def __init__(
        self,
        *,
        id: str,
        name: str | None = None,
        command: str | None = None,
        url: str | None = None,
        transport: str | None = None,
        env: dict[str, str] | None = None,
        mode: ContextMode = ContextMode.default,
        model: Model | None = None,
    ) -> None:
        if not command and not url:
            raise ValueError(f"MCPContextProvider[{id}]: one of `command` or `url` is required")
        super().__init__(id=id, name=name or id, mode=mode, model=model)
        self.command = command
        self.url = url
        self.transport = transport
        self.env = env
        self._mcp_tools: Any = None
        self._agent: Agent | None = None

    def status(self) -> Status:
        target = self.url or self.command
        return Status(ok=True, detail=f"mcp: {target}")

    async def astatus(self) -> Status:
        return self.status()

    def query(self, question: str) -> Answer:
        return answer_from_run(self._ensure_agent().run(question))

    async def aquery(self, question: str) -> Answer:
        return answer_from_run(await self._ensure_agent().arun(question))

    def instructions(self) -> str:
        target = self.url or self.command
        if self.mode == ContextMode.agent:
            return f"`{self.name}`: call `{self.query_tool_name}(question)` to query {target}."
        return f"`{self.name}`: use the tools exposed by the MCP server at {target}."

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    def _default_tools(self) -> list:
        return self._all_tools()

    def _all_tools(self) -> list:
        return [self._ensure_mcp_tools()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_mcp_tools(self) -> MCPTools:
        if self._mcp_tools is None:
            kwargs: dict[str, Any] = {}
            if self.command:
                kwargs["command"] = self.command
            if self.url:
                kwargs["url"] = self.url
            if self.transport:
                kwargs["transport"] = self.transport
            if self.env:
                kwargs["env"] = self.env
            self._mcp_tools = MCPTools(**kwargs)
        return self._mcp_tools

    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        return Agent(
            id=self.id,
            name=self.name,
            role=f"Query the {self.name} MCP server",
            model=self.model,
            tools=[self._ensure_mcp_tools()],
            markdown=True,
        )
