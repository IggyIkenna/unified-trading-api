"""Service status — health, feature freshness, activity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/health")
async def get_service_health(
    request: Request,
    service: str = Query(None),
) -> dict[str, object]:
    """Get health status for all services."""
    svc = get_service(request)
    records = svc.list("service_health", filters={"service": service})
    return {"services": records}


@router.get("/feature-freshness")
async def get_feature_freshness(
    request: Request,
) -> dict[str, object]:
    """Get feature freshness status — last compute time per feature pipeline."""
    svc = get_service(request)
    return {"feature_freshness": svc.list("feature_freshness")}


@router.get("/activity")
async def get_activity(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get recent system activity feed."""
    svc = get_service(request)
    records = svc.list("activity")
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}
