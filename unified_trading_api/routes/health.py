"""Health and readiness endpoints (unauthenticated)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from unified_config_interface import UnifiedCloudConfig

from unified_trading_api import __version__ as _api_version

router = APIRouter()
_cloud_cfg = UnifiedCloudConfig()

_DOMAINS: list[str] = [
    "market-data",
    "execution",
    "positions",
    "analytics",
    "ml",
    "reporting",
    "audit",
    "config",
    "alerts",
    "risk",
    "instruments",
    "documents",
    "deployment",
    "service-status",
    "users",
]


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Standard Cloud Run liveness probe."""
    start_time: float = getattr(request.app.state, "start_time", time.time())
    return {
        "status": "healthy",
        "service": "unified-trading-api",
        "version": _api_version,
        "cloud_provider": _cloud_cfg.cloud_provider,
        "mock_mode": _cloud_cfg.is_mock_mode(),
        "domains": _DOMAINS,
        "uptime_seconds": round(time.time() - start_time, 1),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/readiness")
async def readiness() -> dict[str, str]:
    """Standard Cloud Run readiness probe."""
    return {"status": "ready", "service": "unified-trading-api"}


@router.get("/version")
async def version() -> dict[str, str]:
    """Return service version information."""
    return {"version": _api_version, "service": "unified-trading-api"}
