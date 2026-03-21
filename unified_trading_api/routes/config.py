"""Config domain — system config, venues, feature flags."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/system")
async def get_system_config(
    request: Request,
) -> dict[str, object]:
    """Get system configuration."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("system_config")
        return {"config": records[0] if records else {}}
    return {"error": "real mode not yet wired"}


@router.put("/system")
async def update_system_config(
    request: Request,
) -> dict[str, object]:
    """Update system configuration."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        existing = mock_store.list("system_config")
        if existing:
            existing[0].update(body)
            return {"status": "updated", "config": existing[0]}
        mock_store.add("system_config", body)
        return {"status": "created", "config": body}
    return {"error": "real mode not yet wired"}


@router.get("/venues")
async def get_venue_config(
    request: Request,
) -> dict[str, object]:
    """Get venue configuration."""
    if getattr(request.app.state, "mock_mode", True):
        return {"venues": mock_store.list("config_venues")}
    return {"error": "real mode not yet wired"}


@router.get("/feature-flags")
async def get_feature_flags(
    request: Request,
) -> dict[str, object]:
    """Get feature flags."""
    if getattr(request.app.state, "mock_mode", True):
        return {"feature_flags": mock_store.list("feature_flags")}
    return {"error": "real mode not yet wired"}
