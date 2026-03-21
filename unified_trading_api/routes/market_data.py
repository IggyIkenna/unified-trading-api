"""Market data domain — candles, orderbook, trades, tickers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CandleResponse(BaseModel):
    venue: str
    instrument: str
    timeframe: str
    candles: list[dict[str, float | str | int]]


class OrderBookResponse(BaseModel):
    venue: str
    instrument: str
    depth: int
    bids: list[dict[str, float | str]]
    asks: list[dict[str, float | str]]


class TradesResponse(BaseModel):
    venue: str
    instrument: str
    trades: list[dict[str, float | str | int]]


class TickersResponse(BaseModel):
    venue: str
    tickers: list[dict[str, float | str | int]]


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/candles", response_model=CandleResponse | ErrorResponse)
async def get_candles(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    timeframe: str = Query("1m"),
    limit: int = Query(100),
) -> CandleResponse | ErrorResponse:
    """Get OHLCV candles for an instrument."""
    if getattr(request.app.state, "mock_mode", True):
        return CandleResponse(
            venue=venue,
            instrument=instrument,
            timeframe=timeframe,
            candles=mock_store.list("candles")[:limit],
        )
    return ErrorResponse(error="real mode not yet wired")


@router.get("/orderbook", response_model=OrderBookResponse | ErrorResponse)
async def get_orderbook(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    depth: int = Query(10),
) -> OrderBookResponse | ErrorResponse:
    """Get order book snapshot."""
    if getattr(request.app.state, "mock_mode", True):
        return OrderBookResponse(venue=venue, instrument=instrument, depth=depth, bids=[], asks=[])
    return ErrorResponse(error="real mode not yet wired")


@router.get("/trades", response_model=TradesResponse | ErrorResponse)
async def get_trades(
    request: Request,
    venue: str = Query(...),
    instrument: str = Query(...),
    limit: int = Query(100),
) -> TradesResponse | ErrorResponse:
    """Get recent trades."""
    if getattr(request.app.state, "mock_mode", True):
        return TradesResponse(
            venue=venue,
            instrument=instrument,
            trades=mock_store.list("trades")[:limit],
        )
    return ErrorResponse(error="real mode not yet wired")


@router.get("/tickers", response_model=TickersResponse | ErrorResponse)
async def get_tickers(
    request: Request,
    venue: str = Query(...),
) -> TickersResponse | ErrorResponse:
    """Get all tickers for a venue."""
    if getattr(request.app.state, "mock_mode", True):
        return TickersResponse(venue=venue, tickers=mock_store.list("tickers"))
    return ErrorResponse(error="real mode not yet wired")
