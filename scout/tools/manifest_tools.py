"""Read-only manifest tool — every agent gets this."""

from __future__ import annotations

import json

from agno.tools import tool

from scout.manifest import get_manifest
from scout.tools.redactor import redact


def create_manifest_tool(agent_role: str):
    @tool
    def read_manifest() -> str:
        """Read the current source manifest as it applies to this agent.

        Returns a markdown table listing reachable sources, their mode
        (compile / live-read), capabilities, and current health status.

        Use this BEFORE source_list/source_find/source_read to confirm
        which sources you can talk to right now. Sources marked
        unreachable will refuse calls — don't try them.
        """
        m = get_manifest()
        callable_rows = m.callable_sources(agent_role)
        return redact(
            json.dumps(
                {
                    "built_at": m.built_at,
                    "agent_role": agent_role,
                    "callable_sources": [s.as_dict() for s in callable_rows],
                    "rendered": m.render_for_prompt(agent_role),
                },
                indent=2,
            )
        )

    return read_manifest
