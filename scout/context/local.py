"""LocalContext — agentic read-only context over a local directory.

Wraps an internal Agno agent that has read_file + grep + list_dir
scoped to the configured path. No ingest, no compile.
"""

from __future__ import annotations

from pathlib import Path

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools.coding import CodingTools

from scout.context.base import Answer, HealthState, HealthStatus


class LocalContext:
    """Agentic context over a directory on disk."""

    kind: str = "local"

    def __init__(self, path: str) -> None:
        self.root = Path(path).resolve()
        self.id = f"local:{path}"
        self.name = self.root.name or str(self.root)
        self._agent: Agent | None = None

    def health(self) -> HealthStatus:
        if not self.root.exists():
            return HealthStatus(HealthState.DISCONNECTED, f"{self.root} does not exist")
        if not self.root.is_dir():
            return HealthStatus(HealthState.DISCONNECTED, f"{self.root} is not a directory")
        return HealthStatus(HealthState.CONNECTED, str(self.root))

    def query(
        self,
        question: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> Answer:
        """Ask the internal agent. Returns Answer with text; citation
        hits are inlined in the text for now (Agno's tool calls surface
        paths already)."""
        del filters, limit  # not used by LocalContext today
        agent = self._ensure_agent()
        output = agent.run(question)
        text = output.get_content_as_string() if hasattr(output, "get_content_as_string") else str(output.content)
        return Answer(text=text or "", hits=[])

    # Fresh-per-query today (spec §5.3). Instantiation is cheap; cache if
    # traffic warrants.
    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        return Agent(
            id=f"local-context-{self.root.name or 'root'}",
            name=f"LocalContext({self.root})",
            role="Read-only exploration of a local directory",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=_instructions(self.root),
            tools=[
                CodingTools(
                    base_dir=self.root,
                    enable_read_file=True,
                    enable_grep=True,
                    enable_find=True,
                    enable_ls=True,
                    enable_edit_file=False,
                    enable_write_file=False,
                    enable_run_shell=False,
                ),
            ],
            markdown=True,
        )


def _instructions(root: Path) -> str:
    return f"""\
You are a read-only explorer of the local directory `{root}`.

Answer questions by:
- `list_dir` to see structure
- `grep` to search for keywords
- `read_file` to fetch specific files

Cite file paths (relative to the root) in your answer. Keep responses
concise. If you find nothing relevant, say so explicitly with what you
searched.
"""
