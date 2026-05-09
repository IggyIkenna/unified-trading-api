"""Market data domain — candles, orderbook, trades, tickers."""

from __future__ import annotations

import random as _rng
from datetime import date as _Date  # noqa: N812

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.app_state import (  # noqa: qg-deep-import — self-package
    get_mock_mode,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.batch_candles import (  # noqa: qg-deep-import — self-package
    BatchCandleReader,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/candles")
async def get_candles(
    request: Request,
    instrument: str = Query(...),
    venue: str | None = Query(None),
    timeframe: str = Query("1H"),
    count: int = Query(200, ge=1, le=500),
    mode: str = Query("batch"),
    as_of: _Date | None = Query(None),
    from_date: _Date | None = Query(None),
    to_date: _Date | None = Query(None),
) -> dict[str, object]:
    """Get OHLCV candles for an instrument.

    In mock mode or when venue is absent: returns mock fixture data.
    In real mode with venue: reads from GCS via BatchCandleReader.
    """
    if get_mock_mode(request) or not venue:
        service = get_service(request)
        records = service.list("candles", filters={"instrument": instrument})
        return single_response(records[:count], instrument=instrument, timeframe=timeframe)

    project_id: str | None = getattr(request.app.state.service, "_project_id", None)  # pyright: ignore[reportAny]
    if not project_id:
        return single_response([], instrument=instrument, timeframe=timeframe)

    reader = BatchCandleReader(project_id)
    candles = reader.get_candles(
        venue=venue,
        symbol=instrument,
        timeframe=timeframe,
        limit=count,
        as_of=as_of,
        from_date=from_date,
        to_date=to_date,
    )
    return single_response(candles, instrument=instrument, timeframe=timeframe)


@router.get("/orderbook")
async def get_orderbook(
    request: Request,
    instrument: str = Query(...),
    depth: int = Query(20, ge=1, le=50),
    _venue: str = Query(None),
) -> dict[str, object]:
    """Get order book snapshot — generates dynamic depth in mock mode."""

    service = get_service(request)

    # Try to get last price from tickers
    tickers = service.list("tickers_live", filters={"instrument": instrument})
    if not tickers:
        tickers = service.list("tickers", filters={"instrument": instrument})

    mid_price = float(str(tickers[0].get("price", 100.0))) if tickers else 100.0

    spread_pct = 0.0002  # 2 bps
    half_spread = mid_price * spread_pct

    bids: list[dict[str, float]] = []
    asks: list[dict[str, float]] = []

    for i in range(depth):
        offset = half_spread * (1 + i * 0.5)
        bid_price = mid_price - offset
        ask_price = mid_price + offset
        # Decreasing quantity away from mid
        base_qty = _rng.uniform(0.5, 10.0) / (1 + i * 0.3)  # nosec B311
        bids.append({"price": round(bid_price, 2), "quantity": round(base_qty, 4)})
        asks.append({"price": round(ask_price, 2), "quantity": round(base_qty, 4)})

    return single_response(
        {
            "mid_price": round(mid_price, 2),
            "spread": round(half_spread * 2, 4),
            "bids": bids,
            "asks": asks,
        },
        instrument=instrument,
    )


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
    return paginated_response(records, page, page_size, venue=venue, instrument=instrument)


@router.get("/tickers")
async def get_tickers(
    request: Request,
    venue: str | None = Query(None),
) -> dict[str, object]:
    """Get all tickers for a venue. Real-mode tick aggregation isn't wired
    yet — returns the mock list (or empty in real mode without a backend
    ticker source).
    """
    service = get_service(request)
    return single_response(service.list("tickers"), venue=venue)


@router.get("/fx-rates")
async def get_fx_rates(
    request: Request,
) -> dict[str, object]:
    """Get FX rates for portfolio currency conversion."""
    service = get_service(request)
    records = service.list("fx_rates")
    if records:
        return single_response(records)
    # Fallback static rates
    return single_response(
        [
            {"id": "fx-btc-usd", "pair": "BTC/USD", "rate": 67000.0},
            {"id": "fx-eth-usd", "pair": "ETH/USD", "rate": 3500.0},
            {"id": "fx-usdt-usd", "pair": "USDT/USD", "rate": 1.0001},
            {"id": "fx-eur-usd", "pair": "EUR/USD", "rate": 1.08},
            {"id": "fx-gbp-usd", "pair": "GBP/USD", "rate": 1.27},
        ]
    )
