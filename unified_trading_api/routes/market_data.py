"""Market data domain — candles, orderbook, trades, tickers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/candles")
async def get_candles(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    timeframe: str = Query("1m"),
    limit: int = Query(100),
) -> dict[str, object]:
    """Get OHLCV candles for an instrument."""
    if getattr(request.app.state, "mock_mode", True):
        return {"venue": venue, "instrument": instrument, "timeframe": timeframe, "candles": mock_store.list("candles")[:limit]}
    return {"error": "real mode not yet wired"}


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
    return {"error": "real mode not yet wired"}


@router.get("/trades")
async def get_trades(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    limit: int = Query(100),
) -> dict[str, object]:
    """Get recent trades."""
    if getattr(request.app.state, "mock_mode", True):
        return {"venue": venue, "instrument": instrument, "trades": mock_store.list("trades")[:limit]}
    return {"error": "real mode not yet wired"}


@router.get("/tickers")
async def get_tickers(
    request: Request,
    venue: str = Query(...),
) -> dict[str, object]:
    """Get all tickers for a venue."""
    if getattr(request.app.state, "mock_mode", True):
        return {"venue": venue, "tickers": mock_store.list("tickers")}
    return {"error": "real mode not yet wired"}
