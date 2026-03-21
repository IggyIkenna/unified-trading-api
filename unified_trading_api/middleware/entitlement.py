"""Entitlement middleware — filters responses based on org tier.

Internal users (org_type=internal) see all data.
External users see data scoped by their subscription tier.
In mock mode (DISABLE_AUTH=true), all requests are treated as internal.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from fastapi import Request

logger = logging.getLogger(__name__)


class OrgType(StrEnum):
    """Organization type determining entitlement scope."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class EntitlementContext:
    """Resolved entitlement context for the current request."""

    def __init__(
        self,
        org_id: str,
        org_type: OrgType,
        tier: str = "enterprise",
        scoped_venues: list[str] | None = None,
        max_instruments: int = 10000,
    ) -> None:
        self.org_id = org_id
        self.org_type = org_type
        self.tier = tier
        self.scoped_venues = scoped_venues or []
        self.max_instruments = max_instruments

    @property
    def is_internal(self) -> bool:
        return self.org_type == OrgType.INTERNAL


def get_entitlement_context(request: Request) -> EntitlementContext:
    """Extract entitlement context from request.

    In production: decoded from JWT claims (org_id, org_type, tier).
    In mock mode: returns internal context with full access.
    """
    disable_auth = getattr(request.app.state, "disable_auth", False)
    if disable_auth:
        return EntitlementContext(
            org_id="mock-org",
            org_type=OrgType.INTERNAL,
            tier="enterprise",
        )

    # In real mode, extract from JWT (set by auth middleware upstream)
    auth_claims = getattr(request.state, "auth_claims", {})
    return EntitlementContext(
        org_id=str(auth_claims.get("org_id", "unknown")),
        org_type=OrgType(auth_claims.get("org_type", "external")),
        tier=str(auth_claims.get("tier", "basic")),
        scoped_venues=list(auth_claims.get("scoped_venues", [])),
        max_instruments=int(auth_claims.get("max_instruments", 100)),
    )
