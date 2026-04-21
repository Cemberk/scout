"""Web backend protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from scout.context.provider import Status


@runtime_checkable
class WebBackend(Protocol):
    """A backend for `WebContextProvider`."""

    kind: str

    def status(self) -> Status: ...
    def get_tools(self) -> list: ...
