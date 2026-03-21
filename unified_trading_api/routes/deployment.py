"""Deployment proxy — services, deployments, builds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/services")
async def get_services(
    request: Request,
) -> dict[str, object]:
    """Get registered services and their status."""
    if getattr(request.app.state, "mock_mode", True):
        return {"services": mock_store.list("deployment_services")}
    return {"error": "real mode not yet wired"}


@router.get("/deployments")
async def get_deployments(
    request: Request,
    service: str = Query(None),
    limit: int = Query(50),
) -> dict[str, object]:
    """Get deployment history."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("deployments")
        if service:
            records = [r for r in records if r.get("service") == service]
        return {"deployments": records[:limit]}
    return {"error": "real mode not yet wired"}


@router.get("/builds")
async def get_builds(
    request: Request,
    service: str = Query(None),
    limit: int = Query(50),
) -> dict[str, object]:
    """Get build history."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("builds")
        if service:
            records = [r for r in records if r.get("service") == service]
        return {"builds": records[:limit]}
    return {"error": "real mode not yet wired"}
