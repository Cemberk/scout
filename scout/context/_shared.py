"""Shared helpers used by multiple Context implementations.

Kept private (underscore-prefixed) because it's an implementation detail
of the context layer — callers outside ``scout/context/`` shouldn't
depend on anything here.
"""

from __future__ import annotations

from os import getenv
from pathlib import Path
from typing import Any

from scout.context.base import Answer

_GOOGLE_ENV_VARS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_PROJECT_ID")


def answer_from_run(output: Any) -> Answer:
    """Turn an Agno ``RunOutput`` into an ``Answer``.

    Every agentic context does ``agent.run(question)`` → ``Answer``; this
    is the one-line adapter. Tolerates both shapes Agno has used
    historically (``.get_content_as_string()`` method and ``.content``
    attribute).
    """
    text = output.get_content_as_string() if hasattr(output, "get_content_as_string") else str(output.content)
    return Answer(text=text or "", hits=[])


def google_env_missing() -> str | None:
    """Return a ``missing: [...]`` reason string if any required
    ``GOOGLE_*`` env var is unset, else ``None``.

    Used by ``DriveContext`` + ``GmailContext`` for their health probe
    and for lazy-agent gating.
    """
    missing = [name for name in _GOOGLE_ENV_VARS if not getenv(name)]
    if missing:
        return f"missing: {missing}"
    return None


def google_auth_material_missing() -> str | None:
    """Return a reason string if no Google auth material is available,
    else ``None``.

    Agno's GmailTools / GoogleDriveTools call ``flow.run_local_server()``
    on first use when neither a service-account file nor a ``token.json``
    exists — which opens a browser and blocks in a container. This
    probe lets health checks return DISCONNECTED with a fixit hint
    instead of hanging the startup probe on an OAuth dialog.

    The check matches Agno's priority: service-account env first, then
    ``token.json`` (or ``GMAIL_TOKEN_PATH`` / ``GOOGLE_TOKEN_PATH`` if
    set).
    """
    if getenv("GOOGLE_SERVICE_ACCOUNT_FILE"):
        return None
    token_path = Path(getenv("GMAIL_TOKEN_PATH") or getenv("GOOGLE_TOKEN_PATH") or "token.json")
    if token_path.exists():
        return None
    return f"no Google auth material; run `python scripts/google_auth.py` to create {token_path}"
