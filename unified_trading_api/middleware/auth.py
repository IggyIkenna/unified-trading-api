"""Auth middleware -- API key validation.

In mock mode (DISABLE_AUTH=true), all requests pass through.
In real mode, validates X-API-Key header against UnifiedCloudConfig.
"""

from __future__ import annotations

import logging
from typing import cast

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from unified_config_interface import UnifiedCloudConfig
from unified_events_interface import log_event

from unified_trading_api.services.app_state import get_disable_auth, get_mock_mode

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
        + "Service refuses to start with auth disabled. "
        + "Unset DISABLE_AUTH or set ENVIRONMENT != production."
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
    disable_auth = get_disable_auth(request)
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


async def get_current_user(
    request: Request,
    _: str = Depends(verify_api_key),
) -> dict[str, object]:
    """Extract current user from JWT or X-Demo-Persona header.

    In mock mode with DISABLE_AUTH: extracts persona from header.
    In real mode: would validate JWT from auth-api.
    """
    from unified_trading_api.mock_data.personas import PERSONAS

    disable_auth = get_disable_auth(request)

    # Try X-Demo-Persona header first (mock mode)
    persona_id = request.headers.get("x-demo-persona")
    if persona_id:
        persona = next((p for p in PERSONAS if p["id"] == persona_id), None)
        if persona:
            raw_ent = persona.get("entitlements", [])  # noqa: qg-empty-fallback
            entitlements: list[str] = (
                [str(e) for e in cast(list[object], raw_ent)] if isinstance(raw_ent, list) else []
            )
            return {
                "user_id": str(persona["id"]),
                "org_id": str(persona["org_id"]),
                "role": str(persona["role"]),
                "entitlements": entitlements,
                "display_name": str(persona.get("display_name", "")),  # noqa: qg-empty-fallback
            }

    # Try Authorization Bearer token (JWT from auth-api)
    auth_header = request.headers.get("authorization", "")  # noqa: qg-empty-fallback
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            import jwt as pyjwt

            # In mock mode: use the known dev secret
            # In real mode: would fetch auth-api's public key
            mock_mode = get_mock_mode(request)
            secret = (
                "auth-api-dev-secret-do-not-use-in-production"
                if mock_mode
                else _auth_cfg.get_secret("auth-api-jwt-secret")
            )
            claims = cast(
                dict[str, str | int | list[str]], pyjwt.decode(token, secret, algorithms=["HS256"])
            )
            raw_entitlements = claims.get("entitlements", [])  # noqa: qg-empty-fallback
            return {
                "user_id": str(claims.get("sub", "")),  # noqa: qg-empty-fallback
                "org_id": str(claims.get("org_id", "")),  # noqa: qg-empty-fallback
                "role": str(claims.get("role", "")),  # noqa: qg-empty-fallback
                "entitlements": list(raw_entitlements)
                if isinstance(raw_entitlements, list)
                else [],
                "display_name": str(claims.get("name", claims.get("email", ""))),  # noqa: qg-empty-fallback
            }
        except Exception as exc:
            if not disable_auth:
                logger.warning("JWT validation failed: %s", exc)
                raise HTTPException(status_code=401, detail="Invalid JWT token") from exc
            # In mock mode with disable_auth, fall through to default

    # Default: admin in mock mode
    if disable_auth:
        return {
            "user_id": "admin",
            "org_id": "odum-internal",
            "role": "admin",
            "entitlements": ["*"],
            "display_name": "Admin",
        }

    raise HTTPException(status_code=401, detail="Authentication required")
