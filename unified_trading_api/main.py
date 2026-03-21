"""Unified Trading API — consolidated gateway.

Absorbs 9 domain data API repos into a single FastAPI application
with auth middleware, WebSocket multiplexing, and unified OpenAPI spec.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from unified_config_interface import UnifiedCloudConfig

from unified_trading_api.routes import (
    alerts,
    audit,
    config,
    deployment,
    documents,
    execution,
    health,
    instruments,
    market_data,
    ml,
    positions,
    reporting,
    risk,
    service_status,
    trading_analytics,
    users,
    websocket,
)

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App lifespan -- setup and teardown."""
    app.state.start_time = time.time()

    cloud_config = UnifiedCloudConfig()
    app.state.mock_mode = cloud_config.is_mock_mode()
    app.state.disable_auth = cloud_config.disable_auth

    if app.state.mock_mode:
        logger.info("Starting in MOCK mode -- seeding mock data")
        from unified_trading_api.mock_data.seed import seed_all_domains

        seed_all_domains()
    else:
        logger.info("Starting in REAL mode -- connecting to backend services")

    yield

    logger.info("Shutting down unified-trading-api")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Unified Trading API",
        version=_VERSION,
        description="Consolidated API gateway for the Unified Trading System",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health (unauthenticated)
    app.include_router(health.router, tags=["health"])

    # Domain routers
    app.include_router(market_data.router, prefix="/market-data", tags=["market-data"])
    app.include_router(execution.router, prefix="/execution", tags=["execution"])
    app.include_router(positions.router, prefix="/positions", tags=["positions"])
    app.include_router(trading_analytics.router, prefix="/analytics", tags=["analytics"])
    app.include_router(ml.router, prefix="/ml", tags=["ml"])
    app.include_router(reporting.router, prefix="/reporting", tags=["reporting"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(config.router, prefix="/config", tags=["config"])
    app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
    app.include_router(risk.router, prefix="/risk", tags=["risk"])
    app.include_router(instruments.router, prefix="/instruments", tags=["instruments"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(deployment.router, prefix="/deployment", tags=["deployment"])
    app.include_router(
        service_status.router,
        prefix="/service-status",
        tags=["service-status"],
    )
    app.include_router(users.router, prefix="/users", tags=["users"])

    # WebSocket (unauthenticated connect, auth on subscribe)
    app.include_router(websocket.router, tags=["websocket"])

    return app


def main() -> None:
    """CLI entrypoint."""
    import uvicorn

    uvicorn.run(
        "unified_trading_api.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8030,
    )


if __name__ == "__main__":
    main()
