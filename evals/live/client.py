"""SSE client for POST /teams/{team_id}/runs.

Parses the `event: X / data: <json>` stream agno emits into a flat
RunResult the assertions can chew on. Modelled on ../vibe-video/evals.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TEAM_ID = "scout"


@dataclass
class RunResult:
    final_content: str = ""
    # Every tool call the team + its members made.
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # One entry per delegated member response: {"agent_id", "content"}.
    member_responses: list[dict[str, Any]] = field(default_factory=list)
    # Errors surfaced by the team run (tool errors, model errors, etc.).
    errors: list[str] = field(default_factory=list)
    run_id: str | None = None
    duration_s: float = 0.0


def _parse_sse(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    """Parse an agno SSE stream into `[(event_name, data), ...]`."""
    events: list[tuple[str, dict[str, Any]]] = []
    event_name: str | None = None
    for line in response.iter_lines():
        if not line:
            event_name = None
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            events.append((event_name or data.get("event") or "message", data))
    return events


def run_team(
    prompt: str,
    *,
    team_id: str = DEFAULT_TEAM_ID,
    base_url: str = DEFAULT_BASE_URL,
    timeout_s: float = 600,
) -> RunResult:
    """POST a prompt to /teams/{team_id}/runs and assemble a RunResult."""
    url = f"{base_url.rstrip('/')}/teams/{team_id}/runs"
    form = {"message": prompt, "stream": "true"}

    result = RunResult()
    start = time.monotonic()
    with httpx.Client(timeout=timeout_s) as client:
        with client.stream("POST", url, data=form) as response:
            response.raise_for_status()
            events = _parse_sse(response)
    result.duration_s = time.monotonic() - start

    deltas: list[str] = []
    for event_name, data in events:
        if result.run_id is None:
            result.run_id = data.get("run_id")

        if event_name == "TeamRunContent":
            content = data.get("content")
            if isinstance(content, str):
                deltas.append(content)
        elif event_name == "TeamRunCompleted":
            content = data.get("content")
            if isinstance(content, str) and content:
                result.final_content = content
            for m in data.get("member_responses") or []:
                if isinstance(m, dict):
                    result.member_responses.append({"agent_id": m.get("agent_id"), "content": m.get("content")})
        elif event_name in ("TeamToolCallCompleted", "ToolCallCompleted"):
            tool = data.get("tool") or {}
            result.tool_calls.append(
                {
                    "tool_name": tool.get("tool_name") or tool.get("name"),
                    "arguments": tool.get("tool_args") or tool.get("arguments"),
                    "result": tool.get("result"),
                    "error": tool.get("error"),
                    # Member that made the call, if any.
                    "agent_id": data.get("agent_id"),
                }
            )
        elif event_name in ("TeamToolCallError", "TeamRunError", "ToolCallError", "RunError"):
            msg = data.get("content") or data.get("error") or "(no message)"
            result.errors.append(f"{event_name}: {msg}")

    if not result.final_content:
        result.final_content = "".join(deltas)
    return result
