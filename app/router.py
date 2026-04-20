"""Custom API routes for Scout

GET  /wiki/health              — wiki health
POST /wiki/compile             — trigger compile
POST /wiki/ingest              — ingest url/text
POST /wiki/query               — debug: ask the wiki
GET  /contexts                 — list all contexts + wiki + health
GET  /contexts/{id}/health     — single context or wiki health
POST /contexts/{id}/query      — debug: ask one context/wiki directly
"""

from __future__ import annotations

from typing import Literal

from agno.os.auth import get_authentication_dependency
from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class WikiCompileRequest(BaseModel):
    force: bool = False


class WikiIngestRequest(BaseModel):
    kind: Literal["url", "text"]
    url: str | None = None
    text: str | None = None
    title: str
    tags: list[str] | None = None


class QueryRequest(BaseModel):
    question: str
    limit: int = 10


def _get_wiki():
    from scout.tools.ask_context import get_wiki

    return get_wiki()


def _get_contexts():
    from scout.tools.ask_context import get_contexts

    return get_contexts()


def _target(target_id: str):
    if target_id == "wiki":
        return _get_wiki()
    for ctx in _get_contexts():
        if ctx.id == target_id:
            return ctx
    return None


def _health_row(target) -> dict:
    try:
        h = target.health()
        return {"id": target.id, "kind": target.kind, "state": h.state.value, "detail": h.detail}
    except Exception as exc:
        return {
            "id": getattr(target, "id", "?"),
            "kind": getattr(target, "kind", "?"),
            "state": "disconnected",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def create_router(settings: AgnoAPISettings) -> APIRouter:
    router = APIRouter(
        dependencies=[Depends(get_authentication_dependency(settings))],
    )

    # ------------------------------------------------------------------
    # Wiki
    # ------------------------------------------------------------------

    @router.get("/wiki/health")
    def wiki_health():
        wiki = _get_wiki()
        if wiki is None:
            return JSONResponse({"error": "wiki not configured"}, status_code=503)
        return _health_row(wiki)

    @router.post("/wiki/compile")
    def wiki_compile(body: WikiCompileRequest = WikiCompileRequest()):
        wiki = _get_wiki()
        if wiki is None:
            return JSONResponse({"error": "wiki not configured"}, status_code=503)
        counts = wiki.compile(force=body.force)
        return {"status": "ok", "counts": counts}

    @router.post("/wiki/ingest")
    def wiki_ingest(body: WikiIngestRequest):
        wiki = _get_wiki()
        if wiki is None:
            return JSONResponse({"error": "wiki not configured"}, status_code=503)
        try:
            if body.kind == "url":
                if not body.url:
                    return JSONResponse({"error": "kind=url requires url"}, status_code=400)
                entry = wiki.ingest_url(body.url, title=body.title, tags=body.tags)
            else:
                if body.text is None:
                    return JSONResponse({"error": "kind=text requires text"}, status_code=400)
                entry = wiki.ingest_text(body.text, title=body.title, tags=body.tags)
        except Exception as exc:
            return JSONResponse(
                {"error": f"{type(exc).__name__}: {exc}"},
                status_code=500,
            )
        return {"status": "ingested", "entry_id": entry.id, "name": entry.name, "path": entry.path}

    @router.post("/wiki/query")
    def wiki_query(body: QueryRequest):
        wiki = _get_wiki()
        if wiki is None:
            return JSONResponse({"error": "wiki not configured"}, status_code=503)
        answer = wiki.query(body.question, limit=body.limit)
        return {"text": answer.text, "hits": [h.__dict__ for h in answer.hits]}

    # ------------------------------------------------------------------
    # Contexts
    # ------------------------------------------------------------------

    @router.get("/contexts")
    def list_contexts():
        rows = []
        wiki = _get_wiki()
        if wiki is not None:
            rows.append(_health_row(wiki))
        for ctx in _get_contexts():
            rows.append(_health_row(ctx))
        return rows

    # :path lets target_id contain slashes — contexts like
    # "github:agno-agi/agno" and "s3:bucket/prefix" otherwise 404.
    @router.get("/contexts/{target_id:path}/health")
    def context_health(target_id: str):
        target = _target(target_id)
        if target is None:
            return JSONResponse({"error": f"unknown target {target_id}"}, status_code=404)
        return _health_row(target)

    @router.post("/contexts/{target_id:path}/query")
    def context_query(target_id: str, body: QueryRequest):
        target = _target(target_id)
        if target is None:
            return JSONResponse({"error": f"unknown target {target_id}"}, status_code=404)
        answer = target.query(body.question, limit=body.limit)
        return {"text": answer.text, "hits": [h.__dict__ for h in answer.hits]}

    return router
