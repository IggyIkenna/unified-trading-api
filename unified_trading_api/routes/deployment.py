"""Deployment proxy — services, deployments, builds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/services")
async def get_services(
    request: Request,
) -> dict[str, object]:
    """Get registered services and their status."""
    svc = get_service(request)
    return {"services": svc.list("deployment_services")}


@router.get("/deployments")
async def get_deployments(
    request: Request,
    service: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get deployment history."""
    svc = get_service(request)
    records = svc.list("deployments", filters={"service": service})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/builds")
async def get_builds(
    request: Request,
    service: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get build history."""
    svc = get_service(request)
    records = svc.list("builds", filters={"service": service})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}
