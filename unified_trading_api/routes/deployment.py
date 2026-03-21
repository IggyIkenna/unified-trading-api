"""Deployment proxy — services, deployments, builds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store
from unified_trading_api.models.standard import (
    ErrorDetail,
    StandardErrorResponse,
    paginate,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/services")
async def get_services(
    request: Request,
) -> dict[str, object]:
    """Get registered services and their status."""
    if getattr(request.app.state, "mock_mode", True):
        return {"services": mock_store.list("deployment_services")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/deployments")
async def get_deployments(
    request: Request,
    service: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get deployment history."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("deployments")
        if service:
            records = [r for r in records if r.get("service") == service]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/builds")
async def get_builds(
    request: Request,
    service: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get build history."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("builds")
        if service:
            records = [r for r in records if r.get("service") == service]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
