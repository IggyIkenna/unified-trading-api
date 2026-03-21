"""Users domain — organizations, members, subscriptions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/organizations")
async def get_organizations(
    request: Request,
) -> dict[str, object]:
    """Get organizations."""
    if getattr(request.app.state, "mock_mode", True):
        return {"organizations": mock_store.list("user_organizations")}
    return {"error": "real mode not yet wired"}


@router.get("/members")
async def get_members(
    request: Request,
    organization_id: str = Query(None),
) -> dict[str, object]:
    """Get organization members."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("members")
        if organization_id:
            records = [r for r in records if r.get("organization_id") == organization_id]
        return {"members": records}
    return {"error": "real mode not yet wired"}


@router.get("/subscriptions")
async def get_subscriptions(
    request: Request,
) -> dict[str, object]:
    """Get subscription plans and status."""
    if getattr(request.app.state, "mock_mode", True):
        return {"subscriptions": mock_store.list("subscriptions")}
    return {"error": "real mode not yet wired"}
