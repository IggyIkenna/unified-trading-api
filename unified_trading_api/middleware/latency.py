"""Latency simulation middleware for mock mode.

Adds realistic response delay in interactive mock mode so skeleton
loading states and spinners are visible during demos.
"""

from __future__ import annotations

import asyncio
import random

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class LatencyMiddleware(BaseHTTPMiddleware):
    """Add simulated latency to mock-mode API responses."""

    def __init__(self, app: ASGIApp, base_ms: int = 0) -> None:
        super().__init__(app)
        self.base_ms = base_ms

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.base_ms <= 0:
            return await call_next(request)

        path = request.url.path

        # No latency for health, readiness, WebSocket, admin reset
        if path in ("/health", "/readiness", "/version", "/ws") or path.startswith("/admin"):
            return await call_next(request)

        # Lower latency for POST (snappy actions)
        if request.method == "POST":
            delay_ms = self.base_ms // 3 + random.randint(0, self.base_ms // 6)
        else:
            delay_ms = self.base_ms + random.randint(0, self.base_ms // 2)

        await asyncio.sleep(delay_ms / 1000.0)
        return await call_next(request)
