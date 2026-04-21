"""Custom API routes for Scout

GET  /contexts                 — list all contexts + status
GET  /contexts/{id}/status     — single context status
POST /contexts/{id}/query      — debug: query context directly
"""

from __future__ import annotations

from dataclasses import asdict

from agno.os.auth import get_authentication_dependency
from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from scout.contexts import get_contexts


class QueryRequest(BaseModel):
    question: str
    limit: int = 10


def _target(target_id: str):
    for ctx in get_contexts():
        if ctx.id == target_id:
            return ctx
    return None


def _status_row(target) -> dict:
    try:
        s = target.status()
        return {"id": target.id, "name": target.name, "ok": s.ok, "detail": s.detail}
    except Exception as exc:
        return {
            "id": target.id,
            "name": target.name,
            "ok": False,
            "detail": f"{type(exc).__name__}: {exc}",
        }


def create_router(settings: AgnoAPISettings) -> APIRouter:
    router = APIRouter(
        dependencies=[Depends(get_authentication_dependency(settings))],
    )

    @router.get("/contexts")
    def list_contexts_route():
        return [_status_row(ctx) for ctx in get_contexts()]

    @router.get("/contexts/{target_id:path}/status")
    def context_status(target_id: str):
        target = _target(target_id)
        if target is None:
            return JSONResponse({"error": f"unknown target {target_id}"}, status_code=404)
        return _status_row(target)

    @router.post("/contexts/{target_id:path}/query")
    def context_query(target_id: str, body: QueryRequest):
        target = _target(target_id)
        if target is None:
            return JSONResponse({"error": f"unknown target {target_id}"}, status_code=404)
        answer = target.query(body.question, limit=body.limit)
        return {
            "text": answer.text,
            "results": [asdict(r) for r in answer.results],
        }

    return router
