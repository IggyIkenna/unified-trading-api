"""Auth middleware -- API key validation.

In mock mode (DISABLE_AUTH=true), all requests pass through.
In real mode, validates X-API-Key header against UnifiedCloudConfig.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from unified_config_interface import UnifiedCloudConfig
from unified_events_interface import log_event

logger = logging.getLogger(__name__)

_auth_cfg = UnifiedCloudConfig()
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Production guard
_disable_auth_raw: bool = _auth_cfg.disable_auth
_environment: str = _auth_cfg.environment
if _disable_auth_raw and _environment == "production":
    log_event(
        "AUTH_MISCONFIGURED",
        severity="CRITICAL",
        details={
            "reason": "DISABLE_AUTH_in_production",
            "environment": _environment,
        },
    )
    raise RuntimeError(
        "DISABLE_AUTH=true is forbidden in production. "
        "Service refuses to start with auth disabled. "
        "Unset DISABLE_AUTH or set ENVIRONMENT != production."
    )
DISABLE_AUTH: bool = _disable_auth_raw


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Verify API key from X-API-Key header.

    Returns the validated key. Raises 401 if invalid.
    """
    # Allow override from app.state (set in lifespan)
    disable_auth = getattr(request.app.state, "disable_auth", DISABLE_AUTH)
    if disable_auth:
        return "dev-mode"

    if not api_key:
        log_event(
            "AUTH_FAILURE",
            severity="WARNING",
            details={"auth_type": "api_key", "reason": "missing_key"},
        )
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    expected_key = _auth_cfg.api_key
    if not expected_key or api_key != expected_key:
        log_event(
            "AUTH_FAILURE",
            severity="WARNING",
            details={"auth_type": "api_key", "reason": "invalid_key"},
        )
        raise HTTPException(status_code=401, detail="Invalid API key")

    logger.info("Authentication successful: auth_type=api_key")
    return api_key
