"""Permission Catalogue models — domain/category/permission tree for admin UI.

These are CORRECT-LOCAL API response models (not domain schemas).
The RBAC SSOT (roles, entitlements, tiers) lives in UAC rbac.py.
This module defines the *catalogue browser* response shapes only.
"""

# SCHEMA_PROVENANCE_EXEMPT: CataloguePermission / CatalogueTree / DomainNode /
# PermissionCategory are the catalogue-browser HTTP response shape. The RBAC
# SSOT (Role / Entitlement / Tier) lives in UAC; this module just wraps it for
# the admin UI's tree view and is not imported by other services.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PermissionDomain(StrEnum):
    """Top-level domains in the permission catalogue."""

    PLATFORM_SERVICES = "platform_services"
    DATA_ACCESS = "data_access"
    RESEARCH_ML = "research_ml"
    EXECUTION = "execution"
    REPORTING_REGULATORY = "reporting_regulatory"
    INTERNAL_PROVISIONING = "internal_provisioning"
    ORG_SCOPING = "org_scoping"
    FEATURE_SUBSCRIPTIONS = "feature_subscriptions"


class CataloguePermission(BaseModel):  # CORRECT-LOCAL: API response model
    """A single browsable permission entry."""

    key: str = Field(description="Unique permission key (e.g. 'data_access.venue.binance')")
    label: str = Field(description="Human-readable label")
    description: str = Field(default="", description="Optional longer description")
    domain: PermissionDomain = Field(description="Parent domain")
    category: str = Field(description="Parent category key")
    is_internal_only: bool = Field(
        default=False,
        description="True if this permission is only for internal (staff) users",
    )


class PermissionCategory(BaseModel):  # CORRECT-LOCAL: API response model
    """A category grouping permissions within a domain."""

    key: str = Field(description="Category key (e.g. 'venues')")
    label: str = Field(description="Human-readable label")
    domain: PermissionDomain = Field(description="Parent domain")
    description: str = Field(default="")
    permissions: list[CataloguePermission] = Field(default_factory=list)


class DomainNode(BaseModel):  # CORRECT-LOCAL: API response model
    """A domain node in the catalogue tree."""

    domain: PermissionDomain
    label: str
    description: str = ""
    categories: list[PermissionCategory] = Field(default_factory=list)


class CatalogueTree(BaseModel):  # CORRECT-LOCAL: API response model
    """Full catalogue tree — all 8 domains."""

    domains: list[DomainNode] = Field(default_factory=list)
    total_permissions: int = Field(default=0)
    total_categories: int = Field(default=0)
