"""CLI entry point.

Usage:
    python -m scout                     # interactive chat with the team
    python -m scout contexts            # list registered contexts + status
"""

from __future__ import annotations

import asyncio
import json
import sys


async def _contexts_rows() -> list[dict]:
    from scout.contexts import build_contexts

    rows = []
    for ctx in build_contexts():
        try:
            s = await ctx.astatus()
            rows.append({"id": ctx.id, "name": ctx.name, "ok": s.ok, "detail": s.detail})
        except Exception as exc:
            rows.append({"id": ctx.id, "name": ctx.name, "ok": False, "detail": f"{type(exc).__name__}: {exc}"})
    return rows


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "contexts":
        print(json.dumps(asyncio.run(_contexts_rows()), indent=2))
        return

    from scout.team import scout

    scout.cli_app(stream=True)


if __name__ == "__main__":
    main()
