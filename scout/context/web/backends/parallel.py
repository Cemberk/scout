"""ParallelBackend — web research via Parallel (`parallel-web` SDK).

Exposes two tools:

- `web_search(objective)` — natural-language search; returns URL +
  excerpt pairs.
- `web_extract(url)` — full-content extraction.

Requires `PARALLEL_API_KEY`.
"""

from __future__ import annotations

import json
import logging
from os import getenv

from scout.context.provider import Status

log = logging.getLogger(__name__)


class ParallelBackend:
    """Backend for `WebContextProvider` backed by Parallel's beta API."""

    kind: str = "parallel"

    def __init__(self, *, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else (getenv("PARALLEL_API_KEY", "") or None)

    def status(self) -> Status:
        if not self.api_key:
            return Status(ok=False, detail="PARALLEL_API_KEY not set")
        return Status(ok=True, detail="parallel.ai")

    def get_tools(self) -> list:
        from agno.tools import tool

        api_key = self.api_key

        @tool(name="web_search")
        def web_search(objective: str, max_results: int = 8) -> str:
            """Search the web with a natural-language objective.

            Args:
                objective: What you're trying to find.
                max_results: Upper bound on results (default 8).

            Returns:
                JSON with `results: [{url, title, excerpts: [...]}, ...]`.
            """
            if not api_key:
                return json.dumps({"error": "PARALLEL_API_KEY not configured"})
            try:
                from parallel import Parallel  # type: ignore[import-not-found]

                client = Parallel(api_key=api_key)
                out = client.beta.search(objective=objective, max_results=max_results, mode="agentic")
            except Exception as exc:
                log.exception("web_search failed")
                return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
            results = []
            for r in (out.results or [])[:max_results]:
                results.append(
                    {
                        "url": getattr(r, "url", None),
                        "title": getattr(r, "title", None),
                        "excerpts": [e for e in (getattr(r, "excerpts", None) or [])][:5],
                    }
                )
            return json.dumps({"results": results})

        @tool(name="web_extract")
        def web_extract(url: str) -> str:
            """Fetch a URL's full content as text.

            Args:
                url: The URL to fetch.

            Returns:
                JSON with `{url, content}` or `{error}`.
            """
            if not api_key:
                return json.dumps({"error": "PARALLEL_API_KEY not configured"})
            try:
                from parallel import Parallel  # type: ignore[import-not-found]

                client = Parallel(api_key=api_key)
                result = client.beta.extract(urls=[url], full_content=True)
            except Exception as exc:
                log.exception("web_extract failed for %s", url)
                return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
            if not result or not result.results:
                return json.dumps({"url": url, "content": ""})
            body = result.results[0].full_content or ""
            return json.dumps({"url": url, "content": body[:50_000]})

        return [web_search, web_extract]
