"""Custom API routes for Scout."""

from agno.os.auth import get_authentication_dependency
from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class WikiCompileRequest(BaseModel):
    force: bool = False
    source_id: str | None = None
    entry_id: str | None = None


class WikiIngestRequest(BaseModel):
    title: str
    url: str | None = None
    text: str | None = None
    tags: list[str] = []
    doc_type: str = "article"


def create_router(settings: AgnoAPISettings) -> APIRouter:
    router = APIRouter(
        dependencies=[Depends(get_authentication_dependency(settings))],
    )

    # ------------------------------------------------------------------
    # Liveness
    # ------------------------------------------------------------------

    @router.get("/health")
    def health():
        """Liveness probe — DB reachable?"""
        from sqlalchemy import text

        from db import get_readonly_engine

        try:
            with get_readonly_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as e:
            return JSONResponse({"status": "degraded", "detail": str(e)[:200]}, status_code=503)

    # ------------------------------------------------------------------
    # Manifest + sources
    # ------------------------------------------------------------------

    @router.get("/manifest")
    def get_manifest_endpoint():
        from scout.manifest import get_manifest

        return get_manifest().as_dict()

    @router.get("/sources/{source_id}/health")
    def source_health(source_id: str):
        from scout.sources import get_source

        s = get_source(source_id)
        if s is None:
            return JSONResponse({"error": f"unknown source {source_id}"}, status_code=404)
        h = s.health()
        return {"source_id": source_id, "state": h.state.value, "detail": h.detail}

    # ------------------------------------------------------------------
    # Compile pipeline
    # ------------------------------------------------------------------

    @router.post("/compile/run")
    def run_compile(body: WikiCompileRequest = WikiCompileRequest()):
        """Run the compile pipeline.

        - No body  → compile every compile-on source, skipping unchanged.
        - source_id only → compile that one source.
        - source_id + entry_id → compile a single entry.
        - force=true → re-compile even if hash matches.
        """
        from scout.compile import compile_all, compile_entry, compile_source
        from scout.settings import scout_knowledge
        from scout.sources import get_source

        if body.entry_id:
            if not body.source_id:
                return JSONResponse({"error": "entry_id requires source_id"}, status_code=400)
            s = get_source(body.source_id)
            if s is None:
                return JSONResponse({"error": f"unknown source {body.source_id}"}, status_code=404)
            r = compile_entry(s, body.entry_id, knowledge=scout_knowledge, force=body.force)
            return {
                "status": r.status,
                "wiki_path": r.wiki_path,
                "detail": r.detail,
            }

        if body.source_id:
            results = compile_source(body.source_id, knowledge=scout_knowledge, force=body.force)
            return {
                "source_id": body.source_id,
                "results": [
                    {"entry_id": r.entry_id, "status": r.status, "wiki_path": r.wiki_path, "detail": r.detail}
                    for r in results
                ],
            }

        out = compile_all(knowledge=scout_knowledge, force=body.force)
        summary: dict[str, dict] = {}
        for sid, rs in out.items():
            counts: dict[str, int] = {}
            for r in rs:
                counts[r.status] = counts.get(r.status, 0) + 1
            summary[sid] = {"count": len(rs), "status_counts": counts}
        return {"summary": summary}

    # ------------------------------------------------------------------
    # Wiki ingest
    # ------------------------------------------------------------------

    @router.post("/wiki/ingest")
    def ingest_to_wiki(body: WikiIngestRequest):
        """Ingest a URL or text into context/raw/. JSON body only."""
        if not body.text and not body.url:
            return JSONResponse({"error": "Either url or text is required"}, status_code=400)

        from scout.settings import CONTEXT_RAW_DIR
        from scout.tools.ingest import _do_ingest_text, _do_ingest_url

        if body.text:
            result = _do_ingest_text(
                raw_dir=CONTEXT_RAW_DIR,
                title=body.title,
                content=body.text,
                source=body.url or "api",
                tags=body.tags or None,
                doc_type=body.doc_type,
            )
        else:
            result = _do_ingest_url(
                raw_dir=CONTEXT_RAW_DIR,
                url=body.url,  # type: ignore[arg-type]  # validated above
                title=body.title,
                tags=body.tags or None,
                doc_type=body.doc_type,
            )

        status = result.get("status", "ingested") if isinstance(result, dict) else "ingested"
        return {"status": status, "result": result}

    return router
