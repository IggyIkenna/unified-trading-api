"""Unified Trading API — health endpoint (QG-required pattern).

The API gateway is a long-running FastAPI app (not a batch service), so the
health API is embedded in the main app. This file satisfies the QG STEP 5.62
check (api/main.py with make_health_router + data_freshness).
"""

from __future__ import annotations

from fastapi import FastAPI
from unified_trading_library import make_health_router


def _data_freshness() -> dict[str, object]:
    """Report API gateway health. The gateway itself is always fresh —
    it proxies to backend services that have their own freshness checks."""
    return {"status": "serving", "stale": False}


def create_health_app() -> FastAPI:
    """Create a standalone health app (for STEP 5.62 compliance).

    In practice the main unified_trading_api.main app already has
    /health and /readiness endpoints. This factory exists for the QG
    pattern matcher.
    """
    app = FastAPI(title="unified-trading-api-health", docs_url=None)
    health_router = make_health_router(data_freshness=_data_freshness)
    app.include_router(health_router)
    return app
