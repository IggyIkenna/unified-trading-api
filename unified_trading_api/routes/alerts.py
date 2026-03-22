"""Alerts domain — list, summary, acknowledge, resolve."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

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
    service = get_service(request)
    records = service.list("alerts", filters={"severity": severity, "status": status})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/summary")
async def get_alert_summary(
    request: Request,
) -> dict[str, object]:
    """Get alert summary counts by severity."""
    service = get_service(request)
    return {"summary": service.list("alert_summary")}


@router.post("/acknowledge")
async def acknowledge_alert(
    request: Request,
) -> dict[str, object]:
    """Acknowledge an alert."""
    service = get_service(request)
    body = await request.json()
    alert_id = str(body.get("alert_id", ""))
    updated = service.update("alerts", alert_id, {"status": "acknowledged"})
    if updated:
        return AlertActionResponse(status="acknowledged", alert_id=alert_id).model_dump()
    return {
        "error": {
            "code": "NOT_FOUND",
            "message": "Alert not found",
            "details": {"alert_id": alert_id},
        }
    }


@router.post("/resolve")
async def resolve_alert(
    request: Request,
) -> dict[str, object]:
    """Resolve an alert."""
    service = get_service(request)
    body = await request.json()
    alert_id = str(body.get("alert_id", ""))
    updated = service.update("alerts", alert_id, {"status": "resolved"})
    if updated:
        return AlertActionResponse(status="resolved", alert_id=alert_id).model_dump()
    return {
        "error": {
            "code": "NOT_FOUND",
            "message": "Alert not found",
            "details": {"alert_id": alert_id},
        }
    }
