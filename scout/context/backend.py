"""
Context Provider Backends
=========================

A `ContextBackend` is the I/O layer behind a `ContextProvider`. The
provider owns the agent-facing contract (`query` / `status` /
`get_tools`); the backend owns the actual connection to the source —
an MCP server, an SDK client, a filesystem, a vector DB.

One provider can swap between backends without changing its agent interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from scout.context.provider import Status


class ContextBackend(ABC):
    """Base class for the I/O layer behind a `ContextProvider`."""

    @abstractmethod
    def status(self) -> Status: ...

    @abstractmethod
    def get_tools(self) -> list: ...
