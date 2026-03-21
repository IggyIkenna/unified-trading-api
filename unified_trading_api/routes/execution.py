"""Execution domain — orders, fills, venues, algos, backtests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class OrdersResponse(BaseModel):
    orders: list[dict[str, float | str | int | bool]]


class FillsResponse(BaseModel):
    fills: list[dict[str, float | str | int]]


class VenuesResponse(BaseModel):
    venues: list[dict[str, str | bool | int]]


class AlgosResponse(BaseModel):
    algos: list[dict[str, str | float | int | bool]]


class BacktestsResponse(BaseModel):
    backtests: list[dict[str, str | float | int]]


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=OrdersResponse | ErrorResponse)
async def get_orders(
    request: Request,
    venue: str = Query(None),
    status: str = Query(None),
    limit: int = Query(100),
) -> OrdersResponse | ErrorResponse:
    """Get orders, optionally filtered by venue and status."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("orders")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        if status:
            records = [r for r in records if r.get("status") == status]
        return OrdersResponse(orders=records[:limit])
    return ErrorResponse(error="real mode not yet wired")


@router.get("/fills", response_model=FillsResponse | ErrorResponse)
async def get_fills(
    request: Request,
    venue: str = Query(None),
    order_id: str = Query(None),
    limit: int = Query(100),
) -> FillsResponse | ErrorResponse:
    """Get trade fills."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("fills")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        if order_id:
            records = [r for r in records if r.get("order_id") == order_id]
        return FillsResponse(fills=records[:limit])
    return ErrorResponse(error="real mode not yet wired")


@router.get("/venues", response_model=VenuesResponse | ErrorResponse)
async def get_venues(
    request: Request,
) -> VenuesResponse | ErrorResponse:
    """Get configured execution venues."""
    if getattr(request.app.state, "mock_mode", True):
        return VenuesResponse(venues=mock_store.list("execution_venues"))
    return ErrorResponse(error="real mode not yet wired")


@router.get("/algos", response_model=AlgosResponse | ErrorResponse)
async def get_algos(
    request: Request,
) -> AlgosResponse | ErrorResponse:
    """Get available execution algorithms."""
    if getattr(request.app.state, "mock_mode", True):
        return AlgosResponse(algos=mock_store.list("algos"))
    return ErrorResponse(error="real mode not yet wired")


@router.get("/backtests", response_model=BacktestsResponse | ErrorResponse)
async def get_backtests(
    request: Request,
    limit: int = Query(50),
) -> BacktestsResponse | ErrorResponse:
    """Get backtest runs."""
    if getattr(request.app.state, "mock_mode", True):
        return BacktestsResponse(backtests=mock_store.list("backtests")[:limit])
    return ErrorResponse(error="real mode not yet wired")
