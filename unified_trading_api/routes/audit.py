"""Audit domain — events, compliance, data health, logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/events")
async def get_audit_events(
    request: Request,
    event_type: str = Query(None),
    limit: int = Query(100),
) -> dict[str, object]:
    """Get audit events."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("audit_events")
        if event_type:
            records = [r for r in records if r.get("event_type") == event_type]
        return {"events": records[:limit]}
    return {"error": "real mode not yet wired"}


@router.get("/compliance")
async def get_compliance(
    request: Request,
) -> dict[str, object]:
    """Get compliance check results."""
    if getattr(request.app.state, "mock_mode", True):
        return {"compliance": mock_store.list("compliance")}
    return {"error": "real mode not yet wired"}


@router.get("/data-health")
async def get_data_health(
    request: Request,
) -> dict[str, object]:
    """Get data health metrics."""
    if getattr(request.app.state, "mock_mode", True):
        return {"data_health": mock_store.list("data_health")}
    return {"error": "real mode not yet wired"}


@router.get("/logs")
async def get_audit_logs(
    request: Request,
    service: str = Query(None),
    limit: int = Query(200),
) -> dict[str, object]:
    """Get audit logs."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("audit_logs")
        if service:
            records = [r for r in records if r.get("service") == service]
        return {"logs": records[:limit]}
    return {"error": "real mode not yet wired"}
