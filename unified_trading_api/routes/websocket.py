"""WebSocket endpoint with channel-based multiplexing.

Channels: market-data, positions, alerts, health, execution, analytics.
In mock mode: synthetic ticks with Brownian motion, PnL recalculation.
In real mode: subscribes to PubSub topics via UCI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import defaultdict
from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from unified_trading_library.core.mock_state_store import MockStateStore

from unified_trading_api.services.app_state import get_mock_mode_ws

router = APIRouter()
logger = logging.getLogger(__name__)

_subscriptions: dict[str, set[WebSocket]] = defaultdict(set)


def _build_instruments_from_registry() -> list[dict[str, object]]:
    """Build instrument list from UAC representative_sample.py.

    If UAC import fails (e.g. not installed), falls back to a minimal
    hardcoded set so the WebSocket still works in development.
    """
    from unified_trading_api.mock_data.seed_tickers import BASE_PRICES

    instruments: list[dict[str, object]] = []
    try:
        from unified_api_contracts.registry.representative_sample import (
            CEFI_PERPETUAL_SPECS,
            CEFI_SPOT_SPECS,
            DEFI_INSTRUMENT_SPECS,
            SPORTS_INSTRUMENT_SPECS,
            TRADFI_EQUITY_SPECS,
            TRADFI_FUTURES_SPECS,
        )

        for spec in CEFI_SPOT_SPECS:
            base = str(spec["base"])
            price = BASE_PRICES.get(base, 100.0)
            instruments.append(
                {
                    "instrument": str(spec["symbol"]),
                    "venue": str(spec["venue"]),
                    "price": price,
                    "vol": price * 0.001,
                    "asset_class": "cefi",
                }
            )
        for spec in CEFI_PERPETUAL_SPECS:
            base = str(spec.get("base", spec.get("symbol", "")))
            price = BASE_PRICES.get(base, 67000.0)
            instruments.append(
                {
                    "instrument": str(spec["symbol"]),
                    "venue": str(spec["venue"]),
                    "price": price,
                    "vol": price * 0.0012,
                    "asset_class": "cefi",
                }
            )
        for spec in TRADFI_EQUITY_SPECS:
            sym = str(spec["symbol"])
            price = BASE_PRICES.get(sym, 100.0)
            instruments.append(
                {
                    "instrument": sym,
                    "venue": str(spec["venue"]),
                    "price": price,
                    "vol": price * 0.008,
                    "asset_class": "tradfi",
                }
            )
        for spec in TRADFI_FUTURES_SPECS:
            sym = str(spec["symbol"])
            price = BASE_PRICES.get(sym, 5000.0)
            instruments.append(
                {
                    "instrument": sym,
                    "venue": str(spec["venue"]),
                    "price": price,
                    "vol": price * 0.003,
                    "asset_class": "tradfi",
                }
            )
        for spec in DEFI_INSTRUMENT_SPECS:
            sym = str(spec.get("symbol", spec.get("base", "")))
            price = BASE_PRICES.get(sym, 1.0)
            instruments.append(
                {
                    "instrument": sym,
                    "venue": str(spec["venue"]),
                    "price": price,
                    "vol": price * 0.0001,
                    "asset_class": "defi",
                }
            )
        for spec in SPORTS_INSTRUMENT_SPECS:
            sym = str(spec.get("symbol", spec.get("event_id", "")))
            instruments.append(
                {
                    "instrument": sym,
                    "venue": str(spec["venue"]),
                    "price": 0.55,
                    "vol": 0.02,
                    "asset_class": "sports",
                }
            )
    except (ImportError, KeyError):
        logger.warning("UAC representative_sample not available — using minimal instrument set")
        instruments = [
            {
                "instrument": "BTC-USDT",
                "venue": "binance",
                "price": 67500.0,
                "vol": 80.0,
                "asset_class": "cefi",
            },
            {
                "instrument": "ETH-USDT",
                "venue": "binance",
                "price": 3520.0,
                "vol": 8.0,
                "asset_class": "cefi",
            },
            {
                "instrument": "SOL-USDT",
                "venue": "binance",
                "price": 142.0,
                "vol": 2.5,
                "asset_class": "cefi",
            },
        ]
    return instruments


_INSTRUMENTS: list[dict[str, object]] = _build_instruments_from_registry()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint with channel multiplexing."""
    await websocket.accept()
    client_channels: set[str] = set()
    mock_mode = get_mock_mode_ws(websocket)

    mock_task: asyncio.Task[None] | None = None
    try:
        if mock_mode:
            mock_task = asyncio.create_task(_mock_data_generator(websocket, client_channels))

        while True:
            raw = await websocket.receive_text()
            msg = cast(dict[str, str], json.loads(raw))
            action = msg.get("action")
            channel = msg.get("channel")

            if action == "subscribe" and channel:
                client_channels.add(channel)
                _subscriptions[channel].add(websocket)
                await websocket.send_json({"type": "subscribed", "channel": channel})
                logger.info("Client subscribed to %s", channel)

            elif action == "unsubscribe" and channel:
                client_channels.discard(channel)
                _subscriptions[channel].discard(websocket)
                await websocket.send_json({"type": "unsubscribed", "channel": channel})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        if mock_task is not None:
            mock_task.cancel()
        for ch in client_channels:
            _subscriptions[ch].discard(websocket)


async def _mock_data_generator(websocket: WebSocket, channels: set[str]) -> None:  # noqa: C901
    """Generate mock data with Brownian motion, PnL recalculation."""
    tick_count = 0

    # Initialize price state from instruments
    prices: dict[str, float] = {str(i["instrument"]): float(str(i["price"])) for i in _INSTRUMENTS}
    vols: dict[str, float] = {str(i["instrument"]): float(str(i["vol"])) for i in _INSTRUMENTS}
    venues: dict[str, str] = {str(i["instrument"]): str(i["venue"]) for i in _INSTRUMENTS}

    # Try to get MockStateStore for PnL recalculation
    raw_store = cast(object, getattr(websocket.app.state, "mock_store", None))  # pyright: ignore[reportAny]
    store: MockStateStore | None = raw_store if isinstance(raw_store, MockStateStore) else None

    while True:
        await asyncio.sleep(random.uniform(0.5, 2.0))
        tick_count += 1
        ts = time.time()

        # Market data ticks
        if "market-data" in channels:
            for instrument, price in prices.items():
                vol = vols.get(instrument, 1.0)
                # Brownian motion with mean-reverting drift
                drift = vol * random.gauss(0, 1)
                new_price = max(price + drift, price * 0.8)
                prices[instrument] = new_price

                tick = {
                    "venue": venues.get(instrument, "unknown"),
                    "instrument": instrument,
                    "price": round(new_price, 6 if new_price < 1 else 2),
                    "bid": round(new_price * 0.9999, 6 if new_price < 1 else 2),
                    "ask": round(new_price * 1.0001, 6 if new_price < 1 else 2),
                    "volume": round(random.uniform(0.1, 50.0), 4),
                    "timestamp": ts,
                }
                await websocket.send_json({"channel": "market-data", "type": "tick", "data": tick})

                # Update tickers_live in store
                if store is not None:
                    ticker_data: dict[str, object] = {
                        "price": new_price,
                        "bid": new_price * 0.9999,
                        "ask": new_price * 1.0001,
                        "timestamp": ts,
                    }
                    updated = store.update("tickers_live", instrument, ticker_data)
                    if not updated:
                        store.create(
                            "tickers_live",
                            {
                                "id": instrument,
                                "instrument": instrument,
                                "venue": venues.get(instrument, "unknown"),
                                **ticker_data,
                            },
                        )

        # PnL recalculation every 5 ticks
        if "positions" in channels and tick_count % 5 == 0 and store is not None:
            positions = store.list("positions_live")
            if not positions:
                positions = store.list("positions")

            updated_positions: list[dict[str, object]] = []
            for pos in positions:
                instrument = str(pos.get("instrument", ""))
                entry_price = float(str(pos.get("entry_price", 0)))
                quantity = float(str(pos.get("quantity", 0)))
                side = str(pos.get("side", "long"))
                current_price = prices.get(instrument, entry_price)

                side_mult = 1.0 if side == "long" else -1.0
                fx_rate = float(str(pos.get("fx_rate_to_usd", 1.0)))
                unrealized_pnl = (current_price - entry_price) * quantity * side_mult * fx_rate
                pnl_pct = (
                    ((current_price / entry_price) - 1.0) * 100 * side_mult
                    if entry_price > 0
                    else 0.0
                )

                pos_update: dict[str, object] = {
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "pnl_pct": round(pnl_pct, 4),
                    "mark_price": round(current_price, 2),
                    "last_updated": ts,
                }
                pos_id = str(pos.get("id", ""))
                if pos_id:
                    store.update("positions_live", pos_id, pos_update)

                updated_positions.append({**pos, **pos_update})

            await websocket.send_json(
                {
                    "channel": "positions",
                    "type": "pnl_update",
                    "data": {"positions": updated_positions[:20], "timestamp": ts},
                }
            )

        # Analytics channel — strategy-level PnL aggregation
        if "analytics" in channels and tick_count % 10 == 0 and store is not None:
            positions = store.list("positions_live")
            if not positions:
                positions = store.list("positions")

            strategy_pnl: dict[str, float] = {}
            for pos in positions:
                sid = str(pos.get("strategy_id", "unknown"))
                pnl = float(str(pos.get("unrealized_pnl", 0)))
                strategy_pnl[sid] = strategy_pnl.get(sid, 0) + pnl

            strategies_summary = [
                {"strategy_id": sid, "unrealized_pnl": round(pnl, 2)}
                for sid, pnl in strategy_pnl.items()
            ]

            await websocket.send_json(
                {
                    "channel": "analytics",
                    "type": "pnl_snapshot",
                    "data": {"strategies": strategies_summary, "timestamp": ts},
                }
            )

        # Alert ticks
        if "alerts" in channels and tick_count % 10 == 0:
            await websocket.send_json(
                {
                    "channel": "alerts",
                    "type": "alert",
                    "data": {
                        "alert_id": f"alert-ws-{tick_count}",
                        "severity": random.choice(["low", "medium", "high"]),
                        "message": random.choice(
                            [
                                "Position approaching limit",
                                "Unusual volume detected",
                                "Latency spike on venue",
                                "Strategy drawdown warning",
                            ]
                        ),
                        "timestamp": ts,
                    },
                }
            )

        # Health ticks
        if "health" in channels and tick_count % 15 == 0:
            await websocket.send_json(
                {
                    "channel": "health",
                    "type": "status",
                    "data": {
                        "services_healthy": 21,
                        "services_degraded": random.randint(0, 1),
                        "timestamp": ts,
                    },
                }
            )

        # Execution ticks
        if "execution" in channels and tick_count % 3 == 0:
            instrument = random.choice(list(prices.keys()))
            await websocket.send_json(
                {
                    "channel": "execution",
                    "type": "fill",
                    "data": {
                        "order_id": f"ord-{tick_count}",
                        "status": "filled",
                        "instrument": instrument,
                        "price": round(prices[instrument], 2),
                        "quantity": round(random.uniform(0.01, 2.0), 4),
                        "timestamp": ts,
                    },
                }
            )
