"""Health and readiness endpoints (unauthenticated)."""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Request
from unified_trading_library import UnifiedCloudConfig

from unified_trading_api import __version__ as _api_version
from unified_trading_api.services.app_state import (  # noqa: qg-deep-import — self-package
    get_disable_auth,
    get_mock_mode,
    get_start_time,
)

logger = logging.getLogger(__name__)

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

# Upstream services probed in Tier 2 (live mode).
# Maps env-var name → human-readable service name.
_UPSTREAM_SERVICES: dict[str, str] = {
    "LIVE_SERVICE_STRATEGY_URL": "strategy-service",
    "LIVE_SERVICE_EXECUTION_URL": "execution-service",
    "LIVE_SERVICE_RISK_URL": "risk-service",
    "LIVE_SERVICE_INSTRUMENTS_URL": "instruments-service",
    "LIVE_SERVICE_MARKET_DATA_URL": "market-data-service",
}

_PROBE_TIMEOUT_SECONDS = 2.0


async def _probe_upstream(name: str, url: str) -> dict[str, object]:
    """GET ``{url}/health`` and return a check entry."""
    health_url = f"{url.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_SECONDS) as client:
            resp = await client.get(health_url)
            ok = resp.status_code == 200
            entry: dict[str, object] = {
                "name": name,
                "required_for_tier": 2,
                "ok": ok,
                "url": health_url,
            }
            if not ok:
                entry["error"] = f"HTTP {resp.status_code}"
            return entry
    except httpx.HTTPError as exc:
        return {
            "name": name,
            "required_for_tier": 2,
            "ok": False,
            "url": health_url,
            "error": str(exc),
        }


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

    # Probe upstreams based on tier
    upstream_checks: list[dict[str, object]] = []

    if mock_mode:
        # Tier 1: in-process MockStateStore is always healthy
        upstream_checks.append(
            {"name": "mock-state-store", "required_for_tier": 1, "ok": True, "url": "in-process"}
        )
    else:
        # Tier 2: probe configured upstream service URLs
        for env_var, svc_name in _UPSTREAM_SERVICES.items():
            url = os.environ.get(env_var)  # config-bootstrap:
            if url:
                check = await _probe_upstream(svc_name, url)
                upstream_checks.append(check)

        # Degrade effective tier if any required upstream is down
        failed = [c for c in upstream_checks if c.get("required_for_tier") == 2 and not c.get("ok")]
        if failed:
            effective_tier = min(effective_tier, 1)
            for f in failed:
                degraded_reasons.append(f"upstream {f['name']} unreachable")

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
