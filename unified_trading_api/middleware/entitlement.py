"""Entitlement middleware — filters responses based on org tier.

Internal users (org_type=internal) see all data.
External users see data scoped by their subscription tier.
In mock mode (DISABLE_AUTH=true), all requests are treated as internal.
"""

from __future__ import annotations

import logging
from typing import cast

from fastapi import Request
from unified_api_contracts.internal import OrgType  # noqa: qg-deep-import — UAC internal facade

logger = logging.getLogger(__name__)


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
        self.org_id: str = org_id
        self.org_type: OrgType = org_type
        self.tier: str = tier
        self.scoped_venues: list[str] = scoped_venues if scoped_venues is not None else []
        self.max_instruments: int = max_instruments

    @property
    def is_internal(self) -> bool:
        return self.org_type == OrgType.INTERNAL


def get_entitlement_context(request: Request) -> EntitlementContext:
    """Extract entitlement context from request.

    In production: decoded from JWT claims (org_id, org_type, tier).
    In mock mode: returns internal context with full access.
    """
    disable_auth = cast(bool, getattr(request.app.state, "disable_auth", False))  # pyright: ignore[reportAny]
    if disable_auth:
        return EntitlementContext(
            org_id="mock-org",
            org_type=OrgType.INTERNAL,
            tier="enterprise",
        )

    # In real mode, extract from JWT (set by auth middleware upstream)
    auth_claims: dict[str, object] = getattr(request.state, "auth_claims", {})
    raw_venues = auth_claims.get("scoped_venues", [])  # noqa: qg-empty-fallback
    venues_list: list[str] = [str(v) for v in cast(list[object], raw_venues)] if isinstance(raw_venues, list) else []
    return EntitlementContext(
        org_id=str(auth_claims.get("org_id", "unknown")),
        org_type=OrgType(str(auth_claims.get("org_type", "external"))),
        tier=str(auth_claims.get("tier", "basic")),
        scoped_venues=venues_list,
        max_instruments=int(str(auth_claims.get("max_instruments", 100))),
    )
