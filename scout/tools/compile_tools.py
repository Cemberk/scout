"""
Compile tools — exposed to the Compiler agent.

Thin wrappers around scout.compile.runner so the LLM can drive compilation
on demand (e.g. "compile this one entry") in addition to the cron job.
"""

from __future__ import annotations

import json

from agno.knowledge import Knowledge
from agno.tools import tool

from scout.compile import compile_all, compile_entry, compile_source
from scout.compile_state import list_records_for_source
from scout.manifest import get_manifest
from scout.sources import get_source
from scout.tools.redactor import redact


def create_compile_tools(knowledge: Knowledge):
    @tool
    def list_compile_sources() -> str:
        """Sources currently configured with compile=True (callable by Compiler).

        Returns JSON array of {id, name, mode, capabilities, status}.
        """
        m = get_manifest()
        return redact(json.dumps([s.as_dict() for s in m.compile_sources()], indent=2))

    @tool
    def compile_one(source_id: str, entry_id: str, force: bool = False) -> str:
        """Compile a single entry.

        Args:
            source_id: From list_compile_sources.
            entry_id: Source-local entry id (file path for local sources, file id for Drive).
            force: Re-compile even if source_hash matches.

        Returns JSON: {status, wiki_path, detail}.
        """
        s = get_source(source_id)
        if s is None or not getattr(s, "compile", False):
            return redact(json.dumps({"status": "error", "detail": f"{source_id} is not a compile source"}))
        result = compile_entry(s, entry_id, knowledge=knowledge, force=force)
        return redact(json.dumps({"status": result.status, "wiki_path": result.wiki_path, "detail": result.detail}))

    @tool
    def compile_one_source(source_id: str, force: bool = False, limit: int | None = None) -> str:
        """Compile every entry in a source. Skips already-compiled, unchanged entries.

        Args:
            source_id: Compile-on source id.
            force: Re-compile even if hash matches.
            limit: Cap entries processed (useful when iterating on prompts).

        Returns JSON summary by status.
        """
        results = compile_source(source_id, knowledge=knowledge, force=force, limit=limit)
        summary: dict[str, int] = {}
        for r in results:
            summary[r.status] = summary.get(r.status, 0) + 1
        return redact(json.dumps({"source_id": source_id, "summary": summary, "count": len(results)}))

    @tool
    def compile_all_sources(force: bool = False) -> str:
        """Run the full compile pass over every compile-on source. The cron does this every 10 min."""
        out = compile_all(knowledge=knowledge, force=force)
        per_source: dict[str, dict] = {}
        for sid, results in out.items():
            summary: dict[str, int] = {}
            for r in results:
                summary[r.status] = summary.get(r.status, 0) + 1
            per_source[sid] = {"count": len(results), "summary": summary}
        return redact(json.dumps(per_source, indent=2))

    @tool
    def list_compile_records(source_id: str) -> str:
        """List existing compile records for a source — what's been compiled, when, where to.

        Returns JSON array of {entry_id, source_hash, wiki_path, compiled_at, user_edited}.
        """
        records = list_records_for_source(source_id)
        return redact(
            json.dumps(
                [
                    {
                        "entry_id": r.entry_id,
                        "source_hash": r.source_hash[:12],
                        "wiki_path": r.wiki_path,
                        "compiled_at": r.compiled_at,
                        "user_edited": r.user_edited,
                    }
                    for r in records
                ],
                indent=2,
            )
        )

    return [
        list_compile_sources,
        compile_one,
        compile_one_source,
        compile_all_sources,
        list_compile_records,
    ]
