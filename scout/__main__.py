"""CLI entry point.

Usage:
    python -m scout                     # interactive chat with the team
    python -m scout compile             # run one wiki compile pass
    python -m scout compile --force     # recompile unchanged entries too
    python -m scout contexts            # list registered contexts + wiki health

Invariants that used to live under ``_smoke_gating`` (LocalBackend
path-escape, tool-wiring shape, Context protocol conformance) have
moved to ``python -m evals wiring``.
"""

from __future__ import annotations

import argparse
import json


def _cmd_chat() -> None:
    from scout.team import scout

    scout.cli_app(stream=True)


def _cmd_compile(args: argparse.Namespace) -> None:
    from scout.context.config import build_wiki

    wiki = build_wiki()
    counts = wiki.compile(force=args.force)
    print(json.dumps({"status": "ok", "counts": counts}, indent=2))


def _cmd_contexts() -> None:
    from scout.context.config import build_contexts, build_wiki

    wiki = build_wiki()
    contexts = build_contexts()
    rows = []
    for target in [wiki, *contexts]:
        try:
            h = target.health()
            rows.append(
                {
                    "id": target.id,
                    "name": target.name,
                    "kind": target.kind,
                    "state": h.state.value,
                    "detail": h.detail,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "id": getattr(target, "id", "?"),
                    "name": getattr(target, "name", "?"),
                    "kind": getattr(target, "kind", "?"),
                    "state": "disconnected",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
    print(json.dumps(rows, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="scout")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("chat", help="Interactive chat with the Scout team")

    p_compile = sub.add_parser("compile", help="Run one wiki compile pass")
    p_compile.add_argument("--force", action="store_true", help="Recompile unchanged entries too")

    sub.add_parser("contexts", help="List registered contexts + wiki health")

    args = parser.parse_args()
    if args.cmd == "compile":
        _cmd_compile(args)
    elif args.cmd == "contexts":
        _cmd_contexts()
    else:
        _cmd_chat()


if __name__ == "__main__":
    main()
