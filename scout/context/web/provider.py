"""WebContextProvider — agentic web research.

Wraps a sub-agent whose tools come from the configured backend. Two
backends ship today:

- ``ExaMCPBackend`` — keyless by default via Exa's public MCP server.
- ``ParallelBackend`` — premium, requires ``PARALLEL_API_KEY``.

The backend is chosen at construction; no runtime fallback. Scout's
``build_contexts()`` defaults to Parallel when its key is set, else
Exa MCP — so users get web research on day 1 with no config.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agno.agent import Agent
from agno.models.openai import OpenAIResponses

from scout.context._shared import answer_from_run
from scout.context.base import Answer, ContextProvider, HealthStatus

if TYPE_CHECKING:
    from scout.context.web.backends.exa_mcp import ExaMCPBackend
    from scout.context.web.backends.parallel import ParallelBackend

log = logging.getLogger(__name__)


class WebContextProvider(ContextProvider):
    """Agentic web research. Backend chooses the substrate."""

    kind: str = "web"
    id: str = "web"
    name: str = "Web"

    def __init__(
        self,
        backend: ExaMCPBackend | ParallelBackend,
        *,
        id: str | None = None,
    ) -> None:
        self.backend = backend
        if id is not None:
            self.id = id
        self._agent: Agent | None = None

    def health(self) -> HealthStatus:
        return self.backend.health()

    def query(self, question: str, *, limit: int = 10) -> Answer:
        del limit
        agent = self._ensure_agent()
        return answer_from_run(agent.run(question))

    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        return Agent(
            id=f"web-context-{self.backend.kind}",
            name=f"WebContextProvider({self.backend.kind})",
            role="Research the web and return cited answers",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=_INSTRUCTIONS,
            tools=self.backend.get_tools(),
            markdown=True,
        )


_INSTRUCTIONS = """\
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
