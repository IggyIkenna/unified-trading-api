"""Market data domain — candles, orderbook, trades, tickers."""

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


@router.get("/candles")
async def get_candles(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    timeframe: str = Query("1m"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    """Get OHLCV candles for an instrument."""
    if getattr(request.app.state, "mock_mode", True):
        all_candles = mock_store.list("candles")
        data, pagination = paginate(all_candles, page, page_size)
        return {
            "venue": venue,
            "instrument": instrument,
            "timeframe": timeframe,
            "data": data,
            "pagination": pagination.model_dump(),
        }
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/orderbook")
async def get_orderbook(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    depth: int = Query(10),
) -> dict[str, object]:
    """Get order book snapshot."""
    if getattr(request.app.state, "mock_mode", True):
        return {"venue": venue, "instrument": instrument, "depth": depth, "bids": [], "asks": []}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/trades")
async def get_trades(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    """Get recent trades."""
    if getattr(request.app.state, "mock_mode", True):
        all_trades = mock_store.list("trades")
        data, pagination = paginate(all_trades, page, page_size)
        return {
            "venue": venue,
            "instrument": instrument,
            "data": data,
            "pagination": pagination.model_dump(),
        }
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/tickers")
async def get_tickers(
    request: Request,
    venue: str = Query(...),
) -> dict[str, object]:
    """Get all tickers for a venue."""
    if getattr(request.app.state, "mock_mode", True):
        return {"venue": venue, "tickers": mock_store.list("tickers")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
