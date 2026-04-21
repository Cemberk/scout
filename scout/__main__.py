"""CLI entry point.

Usage:
    python -m scout                     # interactive chat with the team
    python -m scout contexts            # list registered contexts + status
"""

from __future__ import annotations

import argparse
import json


def _cmd_chat() -> None:
    from scout.team import scout

    scout.cli_app(stream=True)


def _cmd_contexts() -> None:
    from scout.contexts import build_contexts

    contexts = build_contexts()
    rows = []
    for ctx in contexts:
        try:
            s = ctx.status()
            rows.append({"id": ctx.id, "name": ctx.name, "ok": s.ok, "detail": s.detail})
        except Exception as exc:
            rows.append(
                {
                    "id": getattr(ctx, "id", "?"),
                    "name": getattr(ctx, "name", "?"),
                    "ok": False,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
    print(json.dumps(rows, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="scout")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("chat", help="Interactive chat with the Scout team")
    sub.add_parser("contexts", help="List registered contexts + status")

    args = parser.parse_args()
    if args.cmd == "contexts":
        _cmd_contexts()
    else:
        _cmd_chat()


if __name__ == "__main__":
    main()
