"""Unified Trading API — consolidated gateway.

Absorbs 9 domain data API repos into a single FastAPI application
with auth middleware, WebSocket multiplexing, and unified OpenAPI spec.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from unified_trading_library import MockStateStore, UnifiedCloudConfig

from unified_trading_api.mock_data.seed import (  # noqa: qg-deep-import — self-package
    SEED_VERSION,
    seed_all_domains,
)
from unified_trading_api.routes import (  # noqa: qg-deep-import — self-package
    admin,
    alerts,
    audit,
    calendar,
    catalogue,
    chat,
    commodity,
    compliance,
    config,
    defi_basis,
    defi_lending,
    defi_liquidation,
    defi_lp,
    deployment,
    derivatives,
    documents,
    events,
    execution,
    health,
    instruments,
    market_data,
    ml,
    positions,
    registry,
    reporting,
    risk,
    service_status,
    sports,
    strategy_performance,
    trading_analytics,
    users,
    websocket,
)
from unified_trading_api.services.mock_service import (  # noqa: qg-deep-import — self-package
    MockDomainService,  # noqa: qg-deep-import — self-package
)

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


_SERVICE_NAME = "unified-trading-api"

# ServiceBootstrap( pattern: The API gateway is a long-running FastAPI app,
# not a batch CLI. Lifecycle events (STARTED/STOPPED) are emitted via the
# lifespan context manager below rather than via ServiceBootstrap operations.
# The api/main.py health endpoint uses make_health_router from UTL.


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App lifespan -- setup and teardown."""
    app.state.start_time = time.time()

    cloud_config = UnifiedCloudConfig()
    app.state.mock_mode = cloud_config.is_mock_mode()
    app.state.disable_auth = cloud_config.disable_auth

    if app.state.mock_mode:
        mock_state_mode = os.environ.get("MOCK_STATE_MODE", "interactive")  # config-bootstrap:
        deterministic = mock_state_mode == "deterministic"

        if deterministic:
            logger.info("MOCK mode (deterministic/CI) — in-memory only, no persistence")
        else:
            logger.info("MOCK mode (interactive) — JSONL persistence in .local-dev-cache/")

        store = MockStateStore("unified-trading-api")

        # Seed version check: if cached version differs, clear and re-seed
        meta = store.list("_meta")
        cached_version = ""
        for m in meta:
            if m.get("id") == "seed_version":
                cached_version = str(m.get("version", ""))  # noqa: qg-empty-fallback
        if cached_version != SEED_VERSION or deterministic:
            if cached_version and cached_version != SEED_VERSION:
                logger.info(
                    "Seed version changed (%s → %s) — clearing cache",
                    cached_version,
                    SEED_VERSION,
                )
            store.reset()
            seed_all_domains(store)
        else:
            logger.info("Seed version %s matches cache — skipping re-seed", SEED_VERSION)

        app.state.service = MockDomainService(store)
        app.state.mock_store = store
    else:
        logger.info("Starting in REAL mode -- wiring GcsDomainService (GCS reader)")
        from unified_trading_api.services.live_service import (  # noqa: qg-deep-import — self-package
            GcsDomainService,  # noqa: qg-deep-import — self-package
        )

        app.state.service = GcsDomainService(
            project_id=cloud_config.gcp_project_id,
        )

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

    # Latency simulation (mock mode only, interactive)
    import os

    mock_latency_ms = int(os.environ.get("MOCK_LATENCY_MS", "0"))  # config-bootstrap:
    if mock_latency_ms > 0:
        from unified_trading_api.middleware.latency import (  # noqa: qg-deep-import — self-package
            LatencyMiddleware,  # noqa: qg-deep-import — self-package
        )

        app.add_middleware(LatencyMiddleware, base_ms=mock_latency_ms)

    # Health + Admin (unauthenticated)
    app.include_router(health.router, tags=["health"])
    app.include_router(reporting.health_router, prefix="/reporting", tags=["reporting"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])

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
    app.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
    app.include_router(registry.router, prefix="/api/v1/registry", tags=["registry"])
    app.include_router(
        strategy_performance.router,
        prefix="/api/v1",
        tags=["strategy-performance"],
    )
    app.include_router(defi_basis.router, prefix="/defi/basis", tags=["defi-basis"])
    app.include_router(defi_lending.router, prefix="/defi/lending", tags=["defi-lending"])
    app.include_router(
        defi_liquidation.router,
        prefix="/defi/liquidation",
        tags=["defi-liquidation"],
    )
    app.include_router(defi_lp.router, prefix="/defi/lp", tags=["defi-lp"])
    app.include_router(derivatives.router, prefix="/derivatives", tags=["derivatives"])

    # Commodity regime trading
    app.include_router(commodity.router, prefix="/commodity", tags=["commodity"])

    # Permission catalogue (admin UI — browse all permissions)
    app.include_router(catalogue.router, prefix="/catalogue", tags=["catalogue"])

    # Calendar (economic results + corporate actions)
    app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])

    # Events (economic calendar, ML predictions, news feed, event positions)
    app.include_router(events.router, prefix="/events", tags=["events"])

    # Help chatbot (public endpoint, tier-gated by auth context)
    app.include_router(chat.router, prefix="/chat", tags=["chat"])

    # Sports fixtures (live scores, odds, leagues)
    app.include_router(sports.router, tags=["sports"])

    # WebSocket (unauthenticated connect, auth on subscribe)
    app.include_router(websocket.router, tags=["websocket"])

    return app


def main() -> None:
    """CLI entrypoint."""
    import uvicorn

    uvicorn.run(
        "unified_trading_api.main:create_app",
        factory=True,
        host="0.0.0.0",  # nosec B104 — Cloud Run requires binding all interfaces
        port=8030,
    )


if __name__ == "__main__":
    main()
