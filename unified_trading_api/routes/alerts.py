"""Alerts domain — list, summary, acknowledge, resolve."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/list")
async def get_alerts(
    request: Request,
    severity: str = Query(None),
    status: str = Query(None),
    limit: int = Query(100),
) -> dict[str, object]:
    """Get alerts list."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("alerts")
        if severity:
            records = [r for r in records if r.get("severity") == severity]
        if status:
            records = [r for r in records if r.get("status") == status]
        return {"alerts": records[:limit]}
    return {"error": "real mode not yet wired"}


@router.get("/summary")
async def get_alert_summary(
    request: Request,
) -> dict[str, object]:
    """Get alert summary counts by severity."""
    if getattr(request.app.state, "mock_mode", True):
        return {"summary": mock_store.list("alert_summary")}
    return {"error": "real mode not yet wired"}


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
            return {"status": "acknowledged", "alert_id": alert_id}
        return {"status": "not_found", "alert_id": alert_id}
    return {"error": "real mode not yet wired"}


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
            return {"status": "resolved", "alert_id": alert_id}
        return {"status": "not_found", "alert_id": alert_id}
    return {"error": "real mode not yet wired"}
