"""Execution domain — orders, fills, venues, algos, backtests."""

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/orders")
async def get_orders(
    request: Request,
    venue: str = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get orders, optionally filtered by venue and status."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("orders")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        if status:
            records = [r for r in records if r.get("status") == status]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/fills")
async def get_fills(
    request: Request,
    venue: str = Query(None),
    order_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get trade fills."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("fills")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        if order_id:
            records = [r for r in records if r.get("order_id") == order_id]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/venues")
async def get_venues(
    request: Request,
) -> dict[str, object]:
    """Get configured execution venues."""
    if getattr(request.app.state, "mock_mode", True):
        return {"venues": mock_store.list("execution_venues")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/algos")
async def get_algos(
    request: Request,
) -> dict[str, object]:
    """Get available execution algorithms."""
    if getattr(request.app.state, "mock_mode", True):
        return {"algos": mock_store.list("algos")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/backtests")
async def get_backtests(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get backtest runs."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("backtests")
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
