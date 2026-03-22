"""Alerts domain — list, summary, acknowledge, escalate, resolve."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/list")
async def get_alerts(
    request: Request,
    severity: str = Query(None),
    status: str = Query(None),
    acknowledged: bool = Query(None),
    mode: str = Query("live", pattern="^(live|batch)$"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get alerts list. mode=live for current, mode=batch for T+1 reconciled."""
    service = get_service(request)
    collection = f"alerts_{mode}"
    filters: dict[str, str | int | float | bool | None] = {"severity": severity, "status": status}
    if acknowledged is not None:
        filters["acknowledged"] = acknowledged
    records = service.list(collection, filters=filters)
    data, pagination = paginate(records, page, page_size)
    return {"mode": mode, "data": data, "pagination": pagination.model_dump(), "as_of": as_of}


@router.get("/summary")
async def get_alert_summary(
    request: Request,
) -> dict[str, object]:
    """Get alert summary counts by severity."""
    service = get_service(request)
    return {"summary": service.list("alert_summary")}


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    request: Request,
    alert_id: str,
) -> dict[str, object]:
    """Acknowledge an alert — sets acknowledged:true with timestamp."""
    service = get_service(request)
    from datetime import UTC, datetime

    updated = service.update(
        "alerts_live",
        alert_id,
        {
            "status": "acknowledged",
            "acknowledged": True,
            "acknowledged_at": datetime.now(UTC).isoformat(),
        },
    )
    if updated:
        return {"status": "acknowledged", "alert": updated}
    return {
        "error": {
            "code": "NOT_FOUND",
            "message": "Alert not found",
            "details": {"alert_id": alert_id},
        }
    }


@router.post("/{alert_id}/escalate")
async def escalate_alert(
    request: Request,
    alert_id: str,
) -> dict[str, object]:
    """Escalate an alert — bumps severity up one level."""
    service = get_service(request)
    alert = service.get("alerts_live", alert_id)
    if not alert:
        return {
            "error": {
                "code": "NOT_FOUND",
                "message": "Alert not found",
                "details": {"alert_id": alert_id},
            }
        }
    severity_ladder = ["low", "medium", "high", "critical"]
    current = str(alert.get("severity", "medium"))
    idx = severity_ladder.index(current) if current in severity_ladder else 1
    new_severity = severity_ladder[min(idx + 1, len(severity_ladder) - 1)]
    from datetime import UTC, datetime

    updated = service.update(
        "alerts_live",
        alert_id,
        {
            "severity": new_severity,
            "escalated_at": datetime.now(UTC).isoformat(),
        },
    )
    return {"status": "escalated", "alert": updated}


@router.get("/active")
async def get_active_alerts(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    severity: str = Query(None),
    acknowledged: bool = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get active alerts with live/batch mode support."""
    service = get_service(request)
    collection = f"alerts_{mode}"
    records = service.list(collection, filters={"severity": severity})
    if acknowledged is not None:
        records = [r for r in records if r.get("acknowledged") == acknowledged]
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination, "mode": mode}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    request: Request,
    alert_id: str,
) -> dict[str, object]:
    """Resolve an alert."""
    service = get_service(request)
    from datetime import UTC, datetime

    updated = service.update(
        "alerts_live",
        alert_id,
        {
            "status": "resolved",
            "resolved_at": datetime.now(UTC).isoformat(),
        },
    )
    if updated:
        return {"status": "resolved", "alert": updated}
    return {
        "error": {
            "code": "NOT_FOUND",
            "message": "Alert not found",
            "details": {"alert_id": alert_id},
        }
    }
