"""Reporting domain — reports, settlements, reconciliation."""

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


@router.get("/reports")
async def get_reports(
    request: Request,
    report_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get generated reports."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("reports")
        if report_type:
            records = [r for r in records if r.get("report_type") == report_type]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/settlements")
async def get_settlements(
    request: Request,
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get settlement reports."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("reporting_settlements")
        if status:
            records = [r for r in records if r.get("status") == status]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/reconciliation")
async def get_reconciliation(
    request: Request,
    date: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get reconciliation results."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("reconciliation")
        if date:
            records = [r for r in records if r.get("date") == date]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
