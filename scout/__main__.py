"""CLI entry point.

Usage:
    python -m scout                     # interactive chat with the team
    python -m scout compile             # run one wiki compile pass
    python -m scout compile --force     # recompile unchanged entries too
    python -m scout contexts            # list registered contexts + wiki health
    python -m scout _smoke_gating       # LocalBackend path-escape guard smoke test
"""

from __future__ import annotations

import argparse
import json
import sys


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


def _cmd_smoke_gating() -> int:
    """Smoke test — LocalBackend refuses to read/write outside its root.

    Without this guard a compromised tool could escape the wiki root. If
    this test ever passes silently, the core path boundary is broken.
    """
    import tempfile
    from pathlib import Path

    from scout.context.backends.local import LocalBackend

    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalBackend(tmp)
        try:
            backend.read_bytes("../escape.txt")
        except ValueError as exc:
            print(f"PASS: LocalBackend.read_bytes raised ValueError — {exc}")
        except Exception as exc:
            print(f"FAIL: read_bytes raised {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        else:
            print("FAIL: LocalBackend.read_bytes accepted ../escape.txt", file=sys.stderr)
            return 1

        try:
            backend.write_bytes("../escape.txt", b"oops")
        except ValueError as exc:
            print(f"PASS: LocalBackend.write_bytes raised ValueError — {exc}")
        except Exception as exc:
            print(f"FAIL: write_bytes raised {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        else:
            escaped = Path(tmp).parent / "escape.txt"
            if escaped.exists():
                escaped.unlink()
            print("FAIL: LocalBackend.write_bytes accepted ../escape.txt", file=sys.stderr)
            return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="scout")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("chat", help="Interactive chat with the Scout team")

    p_compile = sub.add_parser("compile", help="Run one wiki compile pass")
    p_compile.add_argument("--force", action="store_true", help="Recompile unchanged entries too")

    sub.add_parser("contexts", help="List registered contexts + wiki health")
    sub.add_parser(
        "_smoke_gating",
        help="LocalBackend path-escape guard smoke test",
    )

    args = parser.parse_args()
    if args.cmd == "compile":
        _cmd_compile(args)
    elif args.cmd == "contexts":
        _cmd_contexts()
    elif args.cmd == "_smoke_gating":
        sys.exit(_cmd_smoke_gating())
    else:
        _cmd_chat()


if __name__ == "__main__":
    main()
