"""Reporting domain — reports, settlements, reconciliation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/reports")
async def get_reports(
    request: Request,
    report_type: str = Query(None),
    limit: int = Query(50),
) -> dict[str, object]:
    """Get generated reports."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("reports")
        if report_type:
            records = [r for r in records if r.get("report_type") == report_type]
        return {"reports": records[:limit]}
    return {"error": "real mode not yet wired"}


@router.get("/settlements")
async def get_settlements(
    request: Request,
    status: str = Query(None),
) -> dict[str, object]:
    """Get settlement reports."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("reporting_settlements")
        if status:
            records = [r for r in records if r.get("status") == status]
        return {"settlements": records}
    return {"error": "real mode not yet wired"}


@router.get("/reconciliation")
async def get_reconciliation(
    request: Request,
    date: str = Query(None),
) -> dict[str, object]:
    """Get reconciliation results."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("reconciliation")
        if date:
            records = [r for r in records if r.get("date") == date]
        return {"reconciliation": records}
    return {"error": "real mode not yet wired"}
