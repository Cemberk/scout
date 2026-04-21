"""Context/wiki config loader.

Reads SCOUT_WIKI and SCOUT_CONTEXTS env vars, builds the
WikiContextProvider and the list of live-read ContextProviders. Called
once at app startup.

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
    from scout.context.base import ContextProvider
    from scout.context.wiki.provider import WikiContextProvider


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


def build_wiki() -> WikiContextProvider:
    """Read ``SCOUT_WIKI`` env, instantiate the backend, return a
    ``WikiContextProvider``.

    Default: ``SCOUT_WIKI=local:./context`` (``LocalWikiBackend``).
    """
    from scout.context.base import WikiBackend
    from scout.context.wiki.provider import WikiContextProvider

    spec = getenv("SCOUT_WIKI", "local:./context")
    kind, params = parse_spec(spec)

    backend: WikiBackend
    if kind == "local":
        from scout.context.wiki.backends.local import LocalWikiBackend

        backend = LocalWikiBackend(params["path"])
    elif kind == "github":
        from scout.context.wiki.backends.github import GithubWikiBackend

        backend = GithubWikiBackend(params["repo"])
    elif kind == "s3":
        from scout.context.wiki.backends.s3 import S3WikiBackend

        backend = S3WikiBackend(params["bucket"], params["prefix"])
    else:
        raise ValueError(f"SCOUT_WIKI: unsupported backend kind {kind!r}")

    log.info("wiki: %s", spec)
    return WikiContextProvider(backend)


def build_contexts() -> list[ContextProvider]:
    """Read ``SCOUT_CONTEXTS`` env, instantiate each spec, return the list.

    The ``WebContextProvider`` is prepended by default (so Scout can
    answer research questions on day 1 with no config) unless
    ``SCOUT_DISABLE_WEB=true`` is set. Parallel backend wins when
    ``PARALLEL_API_KEY`` is present, else keyless Exa MCP.

    Entries that fail to instantiate are logged and skipped so one
    broken spec doesn't take the app down.
    """
    out: list[ContextProvider] = []

    web = _build_default_web()
    if web is not None:
        out.append(web)
        log.info("context: web (default)")

    raw = getenv("SCOUT_CONTEXTS", "").strip()
    if raw:
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


def _build_default_web() -> ContextProvider | None:
    """Default web provider: Parallel if ``PARALLEL_API_KEY`` is set,
    else keyless Exa MCP. Disable with ``SCOUT_DISABLE_WEB=true``."""
    if getenv("SCOUT_DISABLE_WEB", "").lower() in ("true", "1", "yes"):
        return None
    try:
        from scout.context.web.provider import WebContextProvider

        if getenv("PARALLEL_API_KEY"):
            from scout.context.web.backends.parallel import ParallelBackend

            return WebContextProvider(backend=ParallelBackend())
        from scout.context.web.backends.exa_mcp import ExaMCPBackend

        return WebContextProvider(backend=ExaMCPBackend())
    except Exception:
        log.exception("context: default web provider failed to build; skipping")
        return None


def _build_one(kind: str, params: dict) -> ContextProvider:
    if kind == "local":
        from scout.context.local.provider import LocalContextProvider

        return LocalContextProvider(params["path"])
    if kind == "github":
        from scout.context.github.provider import GithubContextProvider

        return GithubContextProvider(params["repo"])
    if kind == "s3":
        from scout.context.s3.provider import S3ContextProvider

        return S3ContextProvider(params["bucket"], params["prefix"])
    if kind == "slack":
        from scout.context.slack.provider import SlackContextProvider

        return SlackContextProvider()
    if kind == "gmail":
        from scout.context.gmail.provider import GmailContextProvider

        return GmailContextProvider()
    if kind == "drive":
        from scout.context.drive.provider import DriveContextProvider

        return DriveContextProvider()
    raise ValueError(f"unknown context kind {kind!r}")
