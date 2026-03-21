"""Audit domain — events, compliance, data health, logs."""

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


@router.get("/events")
async def get_audit_events(
    request: Request,
    event_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get audit events."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("audit_events")
        if event_type:
            records = [r for r in records if r.get("event_type") == event_type]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/compliance")
async def get_compliance(
    request: Request,
) -> dict[str, object]:
    """Get compliance check results."""
    if getattr(request.app.state, "mock_mode", True):
        return {"compliance": mock_store.list("compliance")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/data-health")
async def get_data_health(
    request: Request,
) -> dict[str, object]:
    """Get data health metrics."""
    if getattr(request.app.state, "mock_mode", True):
        return {"data_health": mock_store.list("data_health")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/logs")
async def get_audit_logs(
    request: Request,
    service: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get audit logs."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("audit_logs")
        if service:
            records = [r for r in records if r.get("service") == service]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
