"""Config domain — system config, venues, feature flags."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/system")
async def get_system_config(
    request: Request,
) -> dict[str, object]:
    """Get system configuration."""
    service = get_service(request)
    records = service.list("system_config")
    return {"config": records[0] if records else {}}


@router.put("/system")
async def update_system_config(
    request: Request,
) -> dict[str, object]:
    """Update system configuration."""
    service = get_service(request)
    body = await request.json()
    existing = service.list("system_config")
    if existing:
        updated = service.update("system_config", "", body)
        if updated:
            return {"status": "updated", "config": updated}
    record = service.create("system_config", body)
    return {"status": "created", "config": record}


@router.get("/venues")
async def get_venue_config(
    request: Request,
) -> dict[str, object]:
    """Get venue configuration."""
    service = get_service(request)
    return {"venues": service.list("config_venues")}


@router.get("/feature-flags")
async def get_feature_flags(
    request: Request,
) -> dict[str, object]:
    """Get feature flags."""
    service = get_service(request)
    return {"feature_flags": service.list("feature_flags")}
