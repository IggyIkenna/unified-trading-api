"""Users domain — organizations, members, subscriptions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginated_response, single_response
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/organizations")
async def get_organizations(
    request: Request,
) -> dict[str, object]:
    """Get organizations."""
    service = get_service(request)
    return single_response(service.list("user_organizations"))


@router.get("/members")
async def get_members(
    request: Request,
    organization_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get organization members."""
    service = get_service(request)
    records = service.list("members", filters={"organization_id": organization_id})
    return paginated_response(records, page, page_size)


@router.get("/subscriptions")
async def get_subscriptions(
    request: Request,
) -> dict[str, object]:
    """Get subscription plans and status."""
    service = get_service(request)
    return single_response(service.list("subscriptions"))
