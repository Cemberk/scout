"""Custom API routes for Scout v3."""

from agno.os.auth import get_authentication_dependency
from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ContextReloadRequest(BaseModel):
    recreate: bool = False


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
    # Context
    # ------------------------------------------------------------------

    @router.post("/context/reload")
    def reload_context(body: ContextReloadRequest = ContextReloadRequest()):
        """Re-index context files into scout_knowledge."""
        from context.load_context import load_context

        loaded = load_context(recreate=body.recreate)
        return {"loaded": loaded, "recreate": body.recreate}

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
        from scout.agents.settings import scout_knowledge
        from scout.compile import compile_all, compile_entry, compile_source
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
        summary = {
            sid: {"count": len(rs), "status_counts": _counts(rs)}
            for sid, rs in out.items()
        }
        return {"summary": summary}

    # ------------------------------------------------------------------
    # Legacy compile/lint endpoints — preserved for compatibility
    # ------------------------------------------------------------------

    @router.post("/wiki/compile")
    def compile_wiki(body: WikiCompileRequest = WikiCompileRequest()):
        """Legacy alias for /compile/run."""
        return run_compile(body)

    @router.post("/wiki/lint")
    async def lint_wiki():
        """Trigger wiki health check via the Linter agent."""
        from scout.team import scout

        response = await scout.arun("Run a health check on the wiki. Write a lint report.")
        content = response.content if response else "No response"
        return {"status": "completed", "response": content}

    @router.post("/wiki/ingest")
    def ingest_to_wiki(body: WikiIngestRequest):
        """Ingest a URL or text into context/raw/."""
        if not body.text and not body.url:
            return JSONResponse(content={"error": "Either url or text is required"}, status_code=400)

        from scout.config import SCOUT_RAW_DIR
        from scout.tools.ingest import _do_ingest_text, _do_ingest_url

        if body.text:
            result = _do_ingest_text(
                raw_dir=SCOUT_RAW_DIR,
                title=body.title,
                content=body.text,
                source=body.url or "api",
                tags=body.tags or None,
                doc_type=body.doc_type,
            )
        else:
            result = _do_ingest_url(
                raw_dir=SCOUT_RAW_DIR,
                url=body.url,  # type: ignore[arg-type]  # validated above
                title=body.title,
                tags=body.tags or None,
                doc_type=body.doc_type,
            )

        return {"status": "ingested", "result": result}

    # ------------------------------------------------------------------
    # Git sync
    # ------------------------------------------------------------------

    @router.post("/sync/pull")
    def sync_pull():
        from scout.config import GIT_SYNC_ENABLED
        from scout.tools.git import run_git

        if not GIT_SYNC_ENABLED:
            return JSONResponse(
                content={"error": "Git sync not configured. Set GITHUB_ACCESS_TOKEN and SCOUT_REPO_URL."},
                status_code=400,
            )

        ok, out = run_git(["pull", "--rebase", "--autostash"])
        return {"status": "ok" if ok else "error", "output": out}

    return router


def _counts(results) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out
