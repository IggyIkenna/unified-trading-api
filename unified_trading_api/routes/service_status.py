"""Service status — health, feature freshness, activity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/health")
async def get_service_health(
    request: Request,
    service: str = Query(None),
) -> dict[str, object]:
    """Get health status for all services."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("service_health")
        if service:
            records = [r for r in records if r.get("service") == service]
        return {"services": records}
    return {"error": "real mode not yet wired"}


@router.get("/feature-freshness")
async def get_feature_freshness(
    request: Request,
) -> dict[str, object]:
    """Get feature freshness status — last compute time per feature pipeline."""
    if getattr(request.app.state, "mock_mode", True):
        return {"feature_freshness": mock_store.list("feature_freshness")}
    return {"error": "real mode not yet wired"}


@router.get("/activity")
async def get_activity(
    request: Request,
    limit: int = Query(50),
) -> dict[str, object]:
    """Get recent system activity feed."""
    if getattr(request.app.state, "mock_mode", True):
        return {"activity": mock_store.list("activity")[:limit]}
    return {"error": "real mode not yet wired"}
