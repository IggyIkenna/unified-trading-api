"""Alerts domain — list, summary, acknowledge, resolve."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store
from unified_trading_api.models.standard import (
    ErrorDetail,
    StandardErrorResponse,
    paginate,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AlertActionResponse(BaseModel):
    status: str
    alert_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/list")
async def get_alerts(
    request: Request,
    severity: str = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get alerts list."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("alerts")
        if severity:
            records = [r for r in records if r.get("severity") == severity]
        if status:
            records = [r for r in records if r.get("status") == status]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/summary")
async def get_alert_summary(
    request: Request,
) -> dict[str, object]:
    """Get alert summary counts by severity."""
    if getattr(request.app.state, "mock_mode", True):
        return {"summary": mock_store.list("alert_summary")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.post("/acknowledge")
async def acknowledge_alert(
    request: Request,
) -> dict[str, object]:
    """Acknowledge an alert."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        alert_id = str(body.get("alert_id", ""))
        updated = mock_store.update("alerts", "alert_id", alert_id, {"status": "acknowledged"})
        if updated:
            return AlertActionResponse(status="acknowledged", alert_id=alert_id).model_dump()
        return StandardErrorResponse(
            error=ErrorDetail(code="NOT_FOUND", message="Alert not found", details={"alert_id": alert_id})
        ).model_dump()
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.post("/resolve")
async def resolve_alert(
    request: Request,
) -> dict[str, object]:
    """Resolve an alert."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        alert_id = str(body.get("alert_id", ""))
        updated = mock_store.update("alerts", "alert_id", alert_id, {"status": "resolved"})
        if updated:
            return AlertActionResponse(status="resolved", alert_id=alert_id).model_dump()
        return StandardErrorResponse(
            error=ErrorDetail(code="NOT_FOUND", message="Alert not found", details={"alert_id": alert_id})
        ).model_dump()
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
