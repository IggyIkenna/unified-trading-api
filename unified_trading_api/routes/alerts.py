"""Alerts domain — list, summary, acknowledge, resolve."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AlertsResponse(BaseModel):
    alerts: list[dict[str, str | int | float | bool]]


class AlertSummaryResponse(BaseModel):
    summary: list[dict[str, str | int]]


class AlertActionResponse(BaseModel):
    status: str
    alert_id: str


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/list", response_model=AlertsResponse | ErrorResponse)
async def get_alerts(
    request: Request,
    severity: str = Query(None),
    status: str = Query(None),
    limit: int = Query(100),
) -> AlertsResponse | ErrorResponse:
    """Get alerts list."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("alerts")
        if severity:
            records = [r for r in records if r.get("severity") == severity]
        if status:
            records = [r for r in records if r.get("status") == status]
        return AlertsResponse(alerts=records[:limit])
    return ErrorResponse(error="real mode not yet wired")


@router.get("/summary", response_model=AlertSummaryResponse | ErrorResponse)
async def get_alert_summary(
    request: Request,
) -> AlertSummaryResponse | ErrorResponse:
    """Get alert summary counts by severity."""
    if getattr(request.app.state, "mock_mode", True):
        return AlertSummaryResponse(summary=mock_store.list("alert_summary"))
    return ErrorResponse(error="real mode not yet wired")


@router.post("/acknowledge", response_model=AlertActionResponse | ErrorResponse)
async def acknowledge_alert(
    request: Request,
) -> AlertActionResponse | ErrorResponse:
    """Acknowledge an alert."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        alert_id = str(body.get("alert_id", ""))
        updated = mock_store.update("alerts", "alert_id", alert_id, {"status": "acknowledged"})
        if updated:
            return AlertActionResponse(status="acknowledged", alert_id=alert_id)
        return AlertActionResponse(status="not_found", alert_id=alert_id)
    return ErrorResponse(error="real mode not yet wired")


@router.post("/resolve", response_model=AlertActionResponse | ErrorResponse)
async def resolve_alert(
    request: Request,
) -> AlertActionResponse | ErrorResponse:
    """Resolve an alert."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        alert_id = str(body.get("alert_id", ""))
        updated = mock_store.update("alerts", "alert_id", alert_id, {"status": "resolved"})
        if updated:
            return AlertActionResponse(status="resolved", alert_id=alert_id)
        return AlertActionResponse(status="not_found", alert_id=alert_id)
    return ErrorResponse(error="real mode not yet wired")
