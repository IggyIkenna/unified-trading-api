"""Audit domain — events, compliance, data health, logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/events")
async def get_audit_events(
    request: Request,
    event_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get audit events."""
    svc = get_service(request)
    records = svc.list("audit_events", filters={"event_type": event_type})
    return paginated_response(records, page, page_size)


@router.get("/compliance")
async def get_compliance(
    request: Request,
) -> dict[str, object]:
    """Get compliance check results."""
    svc = get_service(request)
    return single_response(svc.list("compliance"))


@router.get("/data-health")
async def get_data_health(
    request: Request,
) -> dict[str, object]:
    """Get data health metrics."""
    svc = get_service(request)
    return single_response(svc.list("data_health"))


@router.get("/logs")
async def get_audit_logs(
    request: Request,
    service: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get audit logs."""
    svc = get_service(request)
    records = svc.list("audit_logs", filters={"service": service})
    return paginated_response(records, page, page_size)
