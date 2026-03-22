"""Health and readiness endpoints (unauthenticated)."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from unified_config_interface import UnifiedCloudConfig

from unified_trading_api import __version__ as _api_version
from unified_trading_api.services.app_state import get_disable_auth, get_mock_mode, get_start_time

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
    start_time = get_start_time(request)
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
async def readiness(request: Request) -> dict[str, object]:
    """Runtime readiness with tier detection."""

    mock_mode = get_mock_mode(request)
    disable_auth = get_disable_auth(request)

    # Determine tiers
    declared_tier = 0  # Start with Tier 0
    if mock_mode:
        declared_tier = 1  # Mock mode = Tier 1

    # Check for live service URLs (would indicate Tier 2)
    live_urls_configured = bool(os.environ.get("LIVE_SERVICE_BASE_URL"))  # config-bootstrap:
    if live_urls_configured and not mock_mode:
        declared_tier = 2

    effective_tier = declared_tier
    degraded_reasons: list[str] = []

    # In tier 2, probe upstreams
    upstream_checks: list[dict[str, object]] = []

    return {
        "status": "ready",
        "service": "unified-trading-api",
        "version": _api_version,
        "app_env": _cloud_cfg.environment,
        "mock_mode": mock_mode,
        "disable_auth": disable_auth,
        "declared_runtime_tier": declared_tier,
        "effective_runtime_tier": effective_tier,
        "mock_domain_service": mock_mode,
        "external_data_mocked": mock_mode,
        "upstream_checks": upstream_checks,
        "degraded_reasons": degraded_reasons,
    }


@router.get("/version")
async def version() -> dict[str, str]:
    """Return service version information."""
    return {"version": _api_version, "service": "unified-trading-api"}
