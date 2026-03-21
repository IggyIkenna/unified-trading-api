"""Auth middleware — API key validation.

In mock mode (DISABLE_AUTH=true), all requests pass through.
In real mode, validates X-API-Key header against secret manager.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Verify API key from X-API-Key header.

    Returns the validated key. Raises 401 if invalid.
    """
    disable_auth = getattr(request.app.state, "disable_auth", False)
    if disable_auth:
        return "mock-key"

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    # In production: validate against secret manager / token store
    # For now, accept any non-empty key (real validation wired by Plan G)
    return api_key
