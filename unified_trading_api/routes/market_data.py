"""Market data domain — candles, orderbook, trades, tickers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

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
    service = get_service(request)
    records = service.list("candles")
    data, pagination = paginate(records, page, page_size)
    return {
        "venue": venue,
        "instrument": instrument,
        "timeframe": timeframe,
        "data": data,
        "pagination": pagination.model_dump(),
    }


@router.get("/orderbook")
async def get_orderbook(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    depth: int = Query(10),
) -> dict[str, object]:
    """Get order book snapshot."""
    service = get_service(request)
    book = service.list("orderbook", filters={"venue": venue, "instrument": instrument})
    return {
        "venue": venue,
        "instrument": instrument,
        "depth": depth,
        "bids": book[:depth],
        "asks": book[depth:],
    }


@router.get("/trades")
async def get_trades(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    """Get recent trades."""
    service = get_service(request)
    records = service.list("trades")
    data, pagination = paginate(records, page, page_size)
    return {
        "venue": venue,
        "instrument": instrument,
        "data": data,
        "pagination": pagination.model_dump(),
    }


@router.get("/tickers")
async def get_tickers(
    request: Request,
    venue: str = Query(...),
) -> dict[str, object]:
    """Get all tickers for a venue."""
    service = get_service(request)
    return {"venue": venue, "tickers": service.list("tickers")}
