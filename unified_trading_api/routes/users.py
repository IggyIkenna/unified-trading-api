"""Users domain — organizations, members, subscriptions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store
from unified_trading_api.models.standard import (
    ErrorDetail,
    StandardErrorResponse,
    paginate,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/organizations")
async def get_organizations(
    request: Request,
) -> dict[str, object]:
    """Get organizations."""
    if getattr(request.app.state, "mock_mode", True):
        return {"organizations": mock_store.list("user_organizations")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/members")
async def get_members(
    request: Request,
    organization_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get organization members."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("members")
        if organization_id:
            records = [r for r in records if r.get("organization_id") == organization_id]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/subscriptions")
async def get_subscriptions(
    request: Request,
) -> dict[str, object]:
    """Get subscription plans and status."""
    if getattr(request.app.state, "mock_mode", True):
        return {"subscriptions": mock_store.list("subscriptions")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
