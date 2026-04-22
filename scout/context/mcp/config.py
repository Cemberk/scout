"""
MCP provider env parser
=======================

Turn ``MCP_SERVERS`` + per-slug ``MCP_<SLUG>_*`` env vars into
``MCPContextProvider`` kwargs.

Wire format::

    MCP_SERVERS=linear,github,notion

    MCP_LINEAR_TRANSPORT=stdio
    MCP_LINEAR_COMMAND=npx
    MCP_LINEAR_ARGS=-y,@linear/mcp
    MCP_LINEAR_ENV=LINEAR_API_KEY=${LINEAR_API_KEY}

    MCP_GITHUB_TRANSPORT=streamable-http
    MCP_GITHUB_URL=https://mcp.github.com/mcp
    MCP_GITHUB_HEADERS=Authorization=Bearer ${GITHUB_TOKEN}

    MCP_NOTION_TRANSPORT=sse
    MCP_NOTION_URL=https://mcp.notion.so/sse

Rules:

- ``TRANSPORT`` required for every slug; one of ``stdio``, ``sse``,
  ``streamable-http``.
- stdio: ``COMMAND`` required; ``ARGS`` (comma-separated),
  ``ENV`` (``k=v`` comma-separated) optional.
- sse / streamable-http: ``URL`` required; ``HEADERS`` (``k=v``
  comma-separated, supports ``${VAR}`` interpolation) optional.
- ``${VAR}`` interpolation in ``HEADERS`` and ``ENV`` values: if the
  referenced variable is missing, ``parse_mcp_env`` raises
  ``ValueError``. The registry's graceful-fail pattern turns that into
  a warning and skips the server.
"""

from __future__ import annotations

import re
from os import getenv
from typing import Any

_INTERPOLATION_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def parse_mcp_env(slug: str) -> dict[str, Any]:
    """Read env vars for one slug; return kwargs for ``MCPContextProvider``.

    Raises ``ValueError`` for invalid / incomplete config.
    """
    prefix = f"MCP_{slug.upper()}_"

    def _read(name: str) -> str | None:
        raw = getenv(prefix + name)
        if raw is None:
            return None
        stripped = raw.strip()
        return stripped or None

    transport = _read("TRANSPORT")
    if transport is None:
        raise ValueError(f"{prefix}TRANSPORT is required")
    transport = transport.lower()
    if transport not in ("stdio", "sse", "streamable-http"):
        raise ValueError(f"{prefix}TRANSPORT={transport!r} is not one of stdio/sse/streamable-http")

    kwargs: dict[str, Any] = {
        "server_name": slug,
        "transport": transport,
    }

    if transport == "stdio":
        command = _read("COMMAND")
        if command is None:
            raise ValueError(f"{prefix}COMMAND is required for transport=stdio")
        kwargs["command"] = command
        raw_args = _read("ARGS")
        if raw_args:
            kwargs["args"] = [a.strip() for a in raw_args.split(",") if a.strip()]
        raw_env = _read("ENV")
        if raw_env:
            kwargs["env"] = _parse_kv(raw_env, field=f"{prefix}ENV")
    else:
        url = _read("URL")
        if url is None:
            raise ValueError(f"{prefix}URL is required for transport={transport}")
        kwargs["url"] = url
        raw_headers = _read("HEADERS")
        if raw_headers:
            kwargs["headers"] = _parse_kv(raw_headers, field=f"{prefix}HEADERS")

    timeout = _read("TIMEOUT_SECONDS")
    if timeout:
        try:
            kwargs["timeout_seconds"] = int(timeout)
        except ValueError as exc:
            raise ValueError(f"{prefix}TIMEOUT_SECONDS={timeout!r} is not a valid integer") from exc

    return kwargs


def _parse_kv(raw: str, *, field: str) -> dict[str, str]:
    """Parse a comma-separated ``k=v`` string into a dict with ``${VAR}``
    interpolation on values.
    """
    out: dict[str, str] = {}
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"{field}: expected `key=value`, got {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"{field}: empty key in {item!r}")
        out[key] = _interpolate(value, field=field)
    return out


def _interpolate(value: str, *, field: str) -> str:
    """Expand ``${VAR}`` references against the process environment.

    Missing variables raise ``ValueError`` — the registry catches and
    skips this server rather than silently passing an empty auth header
    that would produce a confusing 401 downstream.
    """

    def _sub(match: re.Match[str]) -> str:
        var = match.group(1)
        resolved = getenv(var)
        if resolved is None:
            raise ValueError(f"{field}: referenced env var ${{{var}}} is not set")
        return resolved

    return _INTERPOLATION_RE.sub(_sub, value)
