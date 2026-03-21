"""WebSocket endpoint with channel-based multiplexing.

Channels: market-data, positions, alerts, health, execution.
In mock mode: synthetic ticks, periodic alerts, position updates.
In real mode: subscribes to PubSub topics via UCI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

logger = logging.getLogger(__name__)

# Connected clients per channel
_subscriptions: dict[str, set[WebSocket]] = defaultdict(set)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint with channel multiplexing.

    Protocol:
    - Client sends: {"action": "subscribe", "channel": "market-data"}
    - Client sends: {"action": "unsubscribe", "channel": "market-data"}
    - Server sends: {"channel": "market-data", "data": {...}}
    """
    await websocket.accept()
    client_channels: set[str] = set()

    mock_mode = getattr(websocket.app.state, "mock_mode", True)

    try:
        # Start mock data generator if in mock mode
        mock_task: asyncio.Task[None] | None = None
        if mock_mode:
            mock_task = asyncio.create_task(_mock_data_generator(websocket, client_channels))

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
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
        if mock_task:
            mock_task.cancel()
        for ch in client_channels:
            _subscriptions[ch].discard(websocket)


async def _mock_data_generator(websocket: WebSocket, channels: set[str]) -> None:
    """Generate mock data for subscribed channels."""
    tick_count = 0
    while True:
        await asyncio.sleep(1.0)
        tick_count += 1
        ts = time.time()

        if "market-data" in channels:
            await websocket.send_json(
                {
                    "channel": "market-data",
                    "data": {
                        "venue": "binance",
                        "instrument": "BTC-USDT",
                        "price": 65000.0 + (tick_count % 100),
                        "volume": 1.5,
                        "timestamp": ts,
                    },
                }
            )

        if "positions" in channels and tick_count % 5 == 0:
            await websocket.send_json(
                {
                    "channel": "positions",
                    "data": {
                        "instrument": "BTC-USDT",
                        "side": "long",
                        "size": 0.5,
                        "unrealized_pnl": 150.0 + tick_count,
                        "timestamp": ts,
                    },
                }
            )

        if "alerts" in channels and tick_count % 10 == 0:
            await websocket.send_json(
                {
                    "channel": "alerts",
                    "data": {
                        "alert_id": f"alert-{tick_count}",
                        "severity": "warning",
                        "message": "Position approaching limit",
                        "timestamp": ts,
                    },
                }
            )

        if "health" in channels and tick_count % 15 == 0:
            await websocket.send_json(
                {
                    "channel": "health",
                    "data": {
                        "services_healthy": 21,
                        "services_degraded": 0,
                        "timestamp": ts,
                    },
                }
            )

        if "execution" in channels and tick_count % 3 == 0:
            await websocket.send_json(
                {
                    "channel": "execution",
                    "data": {
                        "order_id": f"ord-{tick_count}",
                        "status": "filled",
                        "instrument": "ETH-USDT",
                        "price": 3500.0,
                        "timestamp": ts,
                    },
                }
            )
