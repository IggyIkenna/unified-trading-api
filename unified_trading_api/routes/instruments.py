"""Instruments domain — list, catalogue, registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/list")
async def get_instruments(
    request: Request,
    venue: str = Query(None),
    asset_class: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get instruments list."""
    service = get_service(request)
    records = service.list("instruments", filters={"venue": venue, "asset_class": asset_class})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/catalogue")
async def get_catalogue(
    request: Request,
) -> dict[str, object]:
    """Get instrument catalogue with metadata."""
    service = get_service(request)
    return {"catalogue": service.list("instrument_catalogue")}


@router.get("/registry")
async def get_registry(
    request: Request,
) -> dict[str, object]:
    """Get instrument registry — canonical mapping across venues."""
    service = get_service(request)
    return {"registry": service.list("instrument_registry")}
