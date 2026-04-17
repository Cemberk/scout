#!/usr/bin/env python3
"""
Load context manifest into Scout's knowledge base.

Writes compact `File:` metadata entries into `scout_knowledge` for retrieval
routing. Does not ingest raw document contents — FileTools reads those on
demand from the context directory.

Usage:
    python context/load_context.py
    python context/load_context.py --recreate   # clear knowledge index and reload
    python context/load_context.py --dry-run    # preview without writing
"""

from argparse import ArgumentParser
from datetime import UTC, datetime
from pathlib import Path

import yaml

from db import create_knowledge
from scout.config import SCOUT_CONTEXT_DIR

scout_knowledge = create_knowledge("Scout Knowledge", "scout_knowledge")

# File extensions treated as indexable context.
CONTEXT_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json"}


def parse_frontmatter_tags(path: Path) -> list[str] | None:
    """Extract tags from YAML frontmatter if present.

    Expects files starting with '---' delimited YAML containing a 'tags' key.
    Returns None if no frontmatter, no tags, or file does not exist.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    if not text.startswith("---"):
        return None
    # Split on the closing '---' delimiter
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    tags = meta.get("tags")
    if isinstance(tags, list) and tags:
        return sorted(str(t) for t in tags)
    return None


def infer_intent_tags(path: Path, rel_path: str) -> list[str]:
    """Get retrieval intent tags from file frontmatter.

    These are routing hints for the agent's recall step, not content indexes.
    Tags are read from YAML frontmatter in the file. Falls back to
    'general-context' if no frontmatter tags are found.
    """
    return parse_frontmatter_tags(path) or ["general-context"]


def build_metadata_payload(path: Path, rel_path: str) -> str:
    """Build a compact metadata record for a knowledge map entry."""
    tags = infer_intent_tags(path, rel_path)
    size_kb = path.stat().st_size / 1024
    return (
        f"File: {rel_path} in context directory.\n"
        f"Size: {size_kb:.1f} KB\n"
        f"Intent tags: {', '.join(tags)}\n"
        f"Indexed: {datetime.now(UTC).isoformat()}\n"
    )


# Subtrees never indexed as `File:` rows. compiled/ is the wiki — the
# Compiler manages its own `Wiki:` rows. raw/ is compile-only and must
# stay invisible to the Navigator (per spec §7).
_EXCLUDED_TOP_DIRS = {"compiled", "raw"}


def discover_context_files(context_dir: Path) -> list[Path]:
    """Return all indexable context files, sorted by path."""
    if not context_dir.exists():
        return []
    out: list[Path] = []
    for f in context_dir.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in CONTEXT_EXTENSIONS:
            continue
        # Skip compiled/* and raw/* — they have their own indexing path.
        try:
            rel_parts = f.relative_to(context_dir).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] in _EXCLUDED_TOP_DIRS:
            continue
        out.append(f)
    return sorted(out)


def clear_knowledge_index() -> None:
    """Clear the entire scout_knowledge vector store.

    Agno's PgVector doesn't support row-level deletes, so --recreate wipes
    all entries (File:, Schema:, Discovery:, Source:).  The agent will
    rebuild Schema:/Discovery:/Source: entries organically during use.
    """
    print("WARNING: Clearing entire scout_knowledge index (row-level delete not supported).")
    print("         Schema:, Discovery:, and Source: entries will be rebuilt during use.")
    if scout_knowledge.vector_db is not None:
        scout_knowledge.vector_db.delete()


def load_context(*, recreate: bool = False, dry_run: bool = False) -> int:
    """Load context file metadata into scout_knowledge.

    Args:
        recreate: Clear entire knowledge index before loading.
        dry_run: Print what would be loaded without writing.

    Returns:
        Number of files loaded.
    """
    files = discover_context_files(SCOUT_CONTEXT_DIR)
    if not files:
        print(f"No context files found in {SCOUT_CONTEXT_DIR}")
        return 0

    if dry_run:
        print(f"Dry run — {len(files)} file(s) would be loaded:\n")
        for path in files:
            rel = str(path.relative_to(SCOUT_CONTEXT_DIR))
            tags = infer_intent_tags(path, rel)
            size_kb = path.stat().st_size / 1024
            print(f"  {rel}  ({size_kb:.1f} KB)  [{', '.join(tags)}]")
        return len(files)

    if recreate:
        clear_knowledge_index()

    loaded = 0
    for path in files:
        rel_path = str(path.relative_to(SCOUT_CONTEXT_DIR))
        text_content = build_metadata_payload(path=path, rel_path=rel_path)
        scout_knowledge.insert(
            name=f"File: {rel_path}",
            text_content=text_content,
            upsert=True,
        )
        print(f"  Loaded: {rel_path}")
        loaded += 1

    return loaded


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Load context file metadata into scout_knowledge.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Clear entire knowledge index before loading.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview files that would be loaded without writing.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    loaded = load_context(recreate=args.recreate, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"\nLoaded {loaded} file(s) from {SCOUT_CONTEXT_DIR}")


if __name__ == "__main__":
    main()
