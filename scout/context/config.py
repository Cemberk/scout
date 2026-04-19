"""Context/wiki config loader.

Reads SCOUT_WIKI and SCOUT_CONTEXTS env vars, builds the WikiContext
and the list of live-read Contexts. Called once at app startup.

Spec syntax: ``<kind>[:<param>]``

- ``slack`` / ``gmail`` / ``drive`` — no params
- ``local:<path>``
- ``github:<owner/repo>``
- ``s3:<bucket>[/<prefix>]``
"""

from __future__ import annotations

import logging
from os import getenv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scout.context.base import Context
    from scout.context.wiki import WikiContext


log = logging.getLogger(__name__)


_NO_PARAM_KINDS = {"slack", "gmail", "drive"}


def parse_spec(spec: str) -> tuple[str, dict]:
    """Parse a spec string into (kind, params).

    Examples:
        >>> parse_spec("github:owner/repo")
        ('github', {'repo': 'owner/repo'})
        >>> parse_spec("local:/path")
        ('local', {'path': '/path'})
        >>> parse_spec("s3:bucket/prefix/sub")
        ('s3', {'bucket': 'bucket', 'prefix': 'prefix/sub'})
        >>> parse_spec("s3:bucket")
        ('s3', {'bucket': 'bucket', 'prefix': ''})
        >>> parse_spec("slack")
        ('slack', {})
    """
    spec = spec.strip()
    if not spec:
        raise ValueError("empty spec")

    if ":" not in spec:
        kind = spec
        if kind not in _NO_PARAM_KINDS:
            raise ValueError(f"spec {spec!r} requires a parameter")
        return kind, {}

    kind, _, param = spec.partition(":")
    kind = kind.strip()
    param = param.strip()
    if not param:
        raise ValueError(f"spec {spec!r}: param after ':' is empty")

    if kind == "local":
        return kind, {"path": param}
    if kind == "github":
        return kind, {"repo": param}
    if kind == "s3":
        bucket, _, prefix = param.partition("/")
        return kind, {"bucket": bucket, "prefix": prefix}
    raise ValueError(f"unknown spec kind {kind!r} in {spec!r}")


def build_wiki() -> WikiContext:
    """Read ``SCOUT_WIKI`` env, instantiate the backend, return WikiContext.

    Default: ``SCOUT_WIKI=local:./context`` (LocalBackend).
    """
    # Local imports avoid cycles — config is imported before the classes it builds.
    # Several targets land in later sub-steps; type: ignore keeps mypy quiet until then.
    from scout.context.wiki import WikiContext

    spec = getenv("SCOUT_WIKI", "local:./context")
    kind, params = parse_spec(spec)

    if kind == "local":
        from scout.context.backends.local import LocalBackend

        backend = LocalBackend(params["path"])
    elif kind == "github":
        from scout.context.backends.github import GithubBackend  # type: ignore[import-not-found]

        backend = GithubBackend(params["repo"])
    elif kind == "s3":
        from scout.context.backends.s3 import S3Backend  # type: ignore[import-not-found]

        backend = S3Backend(params["bucket"], params["prefix"])
    else:
        raise ValueError(f"SCOUT_WIKI: unsupported backend kind {kind!r}")

    log.info("wiki: %s", spec)
    return WikiContext(backend)


def build_contexts() -> list[Context]:
    """Read ``SCOUT_CONTEXTS`` env, instantiate each spec, return the list.

    Empty list if unset. Entries that fail to instantiate are logged and
    skipped so one broken spec doesn't take the app down.
    """
    raw = getenv("SCOUT_CONTEXTS", "").strip()
    if not raw:
        return []

    out: list[Context] = []
    for spec in (s.strip() for s in raw.split(",") if s.strip()):
        try:
            kind, params = parse_spec(spec)
            ctx = _build_one(kind, params)
        except Exception:
            log.exception("context: failed to build %r; skipping", spec)
            continue
        out.append(ctx)
        log.info("context: %s", spec)
    return out


def _build_one(kind: str, params: dict) -> Context:
    # Several context modules land in later sub-steps; type: ignore keeps
    # mypy quiet until they exist.
    if kind == "local":
        from scout.context.local import LocalContext

        return LocalContext(params["path"])
    if kind == "github":
        from scout.context.github import GithubContext

        return GithubContext(params["repo"])
    if kind == "s3":
        from scout.context.s3 import S3Context  # type: ignore[import-not-found]

        return S3Context(params["bucket"], params["prefix"])
    if kind == "slack":
        from scout.context.slack import SlackContext  # type: ignore[import-not-found]

        return SlackContext()
    if kind == "gmail":
        from scout.context.gmail import GmailContext  # type: ignore[import-not-found]

        return GmailContext()
    if kind == "drive":
        from scout.context.drive import DriveContext  # type: ignore[import-not-found]

        return DriveContext()
    raise ValueError(f"unknown context kind {kind!r}")
