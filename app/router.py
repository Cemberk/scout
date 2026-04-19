"""Custom API routes for Scout v3."""

from agno.os.auth import get_authentication_dependency
from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError


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
    # Manifest + sources
    # ------------------------------------------------------------------

    @router.get("/manifest")
    def get_manifest_endpoint():
        from scout.manifest import get_manifest

        return get_manifest().as_dict()

    @router.post("/manifest/reload")
    def reload_manifest_endpoint():
        from scout.manifest import reload_manifest

        m = reload_manifest()
        return m.as_dict()

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
        summary = {sid: {"count": len(rs), "status_counts": _counts(rs)} for sid, rs in out.items()}
        return {"summary": summary}

    # ------------------------------------------------------------------
    # Legacy compile/lint endpoints — preserved for compatibility
    # ------------------------------------------------------------------

    @router.post("/wiki/compile")
    def compile_wiki(body: WikiCompileRequest = WikiCompileRequest()):
        """Legacy alias for /compile/run."""
        return run_compile(body)

    @router.post("/wiki/ingest")
    async def ingest_to_wiki(request: Request):
        """Ingest a URL or text into context/raw/.

        Expects a JSON body (`WikiIngestRequest`). Sending
        `multipart/form-data` or any other content-type returns a clear
        415 rather than the cryptic `Object of type bytes is not JSON
        serializable` 500 users would otherwise hit when confusing this
        endpoint with `/teams/scout/runs` (which *does* take multipart).
        """
        ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return JSONResponse(
                content={
                    "error": "unsupported content-type",
                    "hint": (
                        "POST application/json with a body like "
                        '{"title": "...", "url": "..." or "text": "..."}. '
                        "/wiki/ingest does not accept form data."
                    ),
                },
                status_code=415,
            )

        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(content={"error": "body is not valid JSON"}, status_code=400)

        try:
            body = WikiIngestRequest.model_validate(payload)
        except ValidationError as e:
            return JSONResponse(content={"error": "invalid body", "detail": e.errors()}, status_code=422)

        if not body.text and not body.url:
            return JSONResponse(content={"error": "Either url or text is required"}, status_code=400)

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

        # _do_ingest_* now return {"status": "ingested"|"duplicate"|"error", ...}
        # per spec §5a. Surface both the raw result and the top-level status.
        status = result.get("status", "ingested") if isinstance(result, dict) else "ingested"
        return {"status": status, "result": result}

    # ------------------------------------------------------------------
    # Doctor — self-health + self-heal
    # ------------------------------------------------------------------

    @router.get("/doctor/health")
    def doctor_health():
        """Liveness ping — never delegates to the Doctor agent, just a
        minimal "am I alive and can I reach the DB" probe."""
        from sqlalchemy import text

        from db import get_readonly_engine

        try:
            with get_readonly_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as e:
            return JSONResponse({"status": "degraded", "detail": str(e)[:200]}, status_code=503)

    @router.post("/doctor/run")
    def doctor_run():
        """Run a diagnostic pass via the Doctor agent.

        Returns the agent's report as JSON. Used by the daily cron and
        available for ad-hoc UI calls. Delivery (Slack post, email) is
        the Leader's job based on what's configured — this endpoint
        just returns the report.
        """
        from scout.agents import doctor

        response = doctor.run(
            "Run a full diagnostic pass. Cover: manifest/source status, "
            "compile state per source, env/integration gaps, anything "
            "stale or broken. Finish with concrete suggested actions "
            "(or 'all green' if everything's fine). Follow the output "
            "shape in your instructions."
        )
        content = getattr(response, "content", None)
        if content is None:
            content = str(response)
        return {"status": "ok", "report": content}

    return router


def _counts(results) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out
