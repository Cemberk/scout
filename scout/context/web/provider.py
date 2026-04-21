"""WebContextProvider — web research via configurable backend.

Backends ship today:

- `ExaMCPBackend` — keyless web search via Exa's public MCP server.
- `ParallelBackend` — premium, requires `PARALLEL_API_KEY`.

Default mode (`ContextMode.default`) exposes the backend's tools
directly — calling agent orchestrates `web_search` / `web_extract` (or
the Exa-named equivalents) itself. Switch to `ContextMode.agent` to
wrap the backend in a sub-agent that does search-then-fetch internally.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agno.agent import Agent
from agno.models.openai import OpenAIResponses

from scout.context._utils import answer_from_run
from scout.context.mode import ContextMode
from scout.context.provider import Answer, ContextProvider, Status

if TYPE_CHECKING:
    from agno.models.base import Model

    from scout.context.web.backend import WebBackend

log = logging.getLogger(__name__)


class WebContextProvider(ContextProvider):
    """Web research. Backend chooses the substrate."""

    def __init__(
        self,
        backend: WebBackend,
        *,
        id: str = "web",
        name: str = "Web",
        mode: ContextMode = ContextMode.default,
        model: Model | None = None,
    ) -> None:
        super().__init__(id=id, name=name, mode=mode, model=model)
        self.backend = backend
        self._agent: Agent | None = None

    def status(self) -> Status:
        return self.backend.status()

    def query(self, question: str, *, limit: int = 10) -> Answer:
        del limit
        agent = self._ensure_agent()
        return answer_from_run(agent.run(question))

    def instructions(self) -> str:
        if self.mode == ContextMode.agent:
            return (
                f"`{self.name}`: call `{self.query_tool_name}(question)` for web research. "
                "Returns a synthesized answer with cited URLs."
            )
        return (
            f"`{self.name}`: search the web for URLs/snippets, then fetch full pages when you need depth. "
            "Cite every URL you use."
        )

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    def _default_tools(self) -> list:
        return self._all_tools()

    def _all_tools(self) -> list:
        return self.backend.get_tools()

    # ------------------------------------------------------------------
    # Sub-agent — built lazily for agent mode and programmatic query()
    # ------------------------------------------------------------------

    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        return Agent(
            id=f"web-context-{self.backend.kind}",
            name=f"WebContextProvider({self.backend.kind})",
            role="Research the web and return cited answers",
            model=self.model or OpenAIResponses(id="gpt-5.4"),
            instructions=_AGENT_INSTRUCTIONS,
            tools=self.backend.get_tools(),
            markdown=True,
        )


_AGENT_INSTRUCTIONS = """\
You answer questions by searching the web and reading relevant pages.

Workflow:

1. **Search first.** Use the search tool with a focused natural-language
   query. Read the top URLs + excerpts.
2. **Fetch when depth is needed.** If the question asks about a specific
   URL, or the excerpts don't answer it, fetch the page(s) and read.
3. **Synthesize from at least two sources** when possible. Cross-check.
4. **Cite every URL you used.** Inline links are fine; include them so
   the caller can verify.
5. **Say so plainly** if the web doesn't have a confident answer.

You are read-only. Never submit forms, never follow redirects to auth
flows, never output credentials.
"""
