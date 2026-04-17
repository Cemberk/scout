"""CLI entry point.

Usage:
    python -m scout                              # interactive chat with the team
    python -m scout compile                      # compile every compile-on source
    python -m scout compile --source local:raw   # one source
    python -m scout compile --source local:raw --entry handbook.pdf   # one entry
    python -m scout compile --force              # re-compile even if hash matches
    python -m scout manifest                     # print current manifest
    python -m scout sources                      # list all registered sources + capabilities
"""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_chat() -> None:
    from scout.team import scout

    scout.cli_app(stream=True)


def _cmd_compile(args: argparse.Namespace) -> None:
    from scout.agents.settings import scout_knowledge
    from scout.compile import compile_all, compile_entry, compile_source
    from scout.sources import get_source

    if args.entry:
        if not args.source:
            print("--entry requires --source", file=sys.stderr)
            sys.exit(2)
        s = get_source(args.source)
        if s is None:
            print(f"unknown source: {args.source}", file=sys.stderr)
            sys.exit(2)
        r = compile_entry(s, args.entry, knowledge=scout_knowledge, force=args.force)
        print(json.dumps({"status": r.status, "wiki_path": r.wiki_path, "detail": r.detail}, indent=2))
        return

    if args.source:
        results = compile_source(args.source, knowledge=scout_knowledge, force=args.force, limit=args.limit)
        for r in results:
            print(f"  [{r.status}] {r.entry_id} -> {r.wiki_path or '-'}  {r.detail}")
        return

    out = compile_all(knowledge=scout_knowledge, force=args.force)
    for sid, results in out.items():
        print(f"\n=== {sid} ({len(results)} entries) ===")
        for r in results:
            print(f"  [{r.status}] {r.entry_id} -> {r.wiki_path or '-'}  {r.detail}")


def _cmd_manifest() -> None:
    from scout.manifest import reload_manifest

    print(json.dumps(reload_manifest().as_dict(), indent=2))


def _cmd_sources() -> None:
    from scout.sources import get_sources

    rows = []
    for s in get_sources():
        h = s.health()
        rows.append(
            {
                "id": s.id,
                "name": s.name,
                "kind": type(s).__name__,
                "compile": getattr(s, "compile", False),
                "live_read": getattr(s, "live_read", False),
                "capabilities": sorted(c.value for c in s.capabilities()),
                "status": h.state.value,
                "detail": h.detail,
            }
        )
    print(json.dumps(rows, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="scout")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("chat", help="Interactive chat with the Scout team")

    p_compile = sub.add_parser("compile", help="Run the compile pipeline")
    p_compile.add_argument("--source", help="Source id (e.g. local:raw)")
    p_compile.add_argument("--entry", help="Single entry id within the source")
    p_compile.add_argument("--force", action="store_true", help="Re-compile even if unchanged")
    p_compile.add_argument("--limit", type=int, help="Cap entries processed (per source)")

    sub.add_parser("manifest", help="Print the current source manifest")
    sub.add_parser("sources", help="List all registered sources + capabilities")

    args = parser.parse_args()
    if args.cmd == "compile":
        _cmd_compile(args)
    elif args.cmd == "manifest":
        _cmd_manifest()
    elif args.cmd == "sources":
        _cmd_sources()
    else:
        # No subcommand → drop into chat (back-compat with `python -m scout`)
        _cmd_chat()


if __name__ == "__main__":
    main()
