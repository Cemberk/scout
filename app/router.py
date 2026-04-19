"""Custom API routes for Scout.

Endpoints land in 1n (§7.5). This file is a placeholder — it registers
no routes so the old manifest / source / compile endpoints are gone
but the router can still be wired into FastAPI.
"""

from agno.os.auth import get_authentication_dependency
from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends


def create_router(settings: AgnoAPISettings) -> APIRouter:
    router = APIRouter(
        dependencies=[Depends(get_authentication_dependency(settings))],
    )
    return router
