"""ExaMCPBackend — keyless (or keyed) web search via Exa's public MCP server.

Exposes Exa's `web_search_exa` + `web_fetch_exa` tools to the
``WebContextProvider``'s sub-agent. The default endpoint is keyless;
passing ``api_key`` (or setting ``EXA_API_KEY``) raises the rate ceiling.
"""

from __future__ import annotations

import logging
from os import getenv
from typing import Any

from scout.context.base import HealthState, HealthStatus

log = logging.getLogger(__name__)

_BASE_URL = "https://mcp.exa.ai/mcp"
_TOOLS = "web_search_exa,web_fetch_exa"


class ExaMCPBackend:
    """Backend for ``WebContextProvider`` that speaks to Exa's MCP server."""

    kind: str = "exa_mcp"

    def __init__(self, *, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else (getenv("EXA_API_KEY", "") or None)
        if self.api_key:
            self.url = f"{_BASE_URL}?exaApiKey={self.api_key}&tools={_TOOLS}"
        else:
            self.url = f"{_BASE_URL}?tools={_TOOLS}"
        self._mcp_tools: Any = None  # lazy — MCPTools creates a client on first use

    def health(self) -> HealthStatus:
        # The MCP endpoint is public; we don't ping it here to avoid a
        # network round-trip on every health probe. If the endpoint is
        # down, the first query surfaces the error in the model's output
        # via the MCP tool's own error path.
        detail = f"mcp.exa.ai ({'keyed' if self.api_key else 'keyless'})"
        return HealthStatus(HealthState.CONNECTED, detail)

    def get_tools(self) -> list:
        """Return MCPTools wired to the Exa endpoint (cached)."""
        if self._mcp_tools is None:
            from agno.tools.mcp import MCPTools

            self._mcp_tools = MCPTools(url=self.url, transport="streamable-http")
        return [self._mcp_tools]
