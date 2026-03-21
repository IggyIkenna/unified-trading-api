"""Instruments domain — list, catalogue, registry."""

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


@router.get("/list")
async def get_instruments(
    request: Request,
    venue: str = Query(None),
    asset_class: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get instruments list."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("instruments")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        if asset_class:
            records = [r for r in records if r.get("asset_class") == asset_class]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/catalogue")
async def get_catalogue(
    request: Request,
) -> dict[str, object]:
    """Get instrument catalogue with metadata."""
    if getattr(request.app.state, "mock_mode", True):
        return {"catalogue": mock_store.list("instrument_catalogue")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/registry")
async def get_registry(
    request: Request,
) -> dict[str, object]:
    """Get instrument registry — canonical mapping across venues."""
    if getattr(request.app.state, "mock_mode", True):
        return {"registry": mock_store.list("instrument_registry")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
