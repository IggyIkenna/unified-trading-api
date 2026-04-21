"""Permission Catalogue routes — browse all permissions by domain/category.

Provides a read-only API for the admin UI to browse the full permission tree.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.permission_catalogue import (  # noqa: qg-deep-import — self-package
    PermissionDomain,
)
from unified_trading_api.models.permission_catalogue_data import (  # noqa: qg-deep-import — self-package
    PERMISSION_CATALOGUE,  # noqa: qg-deep-import — self-package
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("")
async def get_catalogue() -> dict[str, object]:
    """Return the full permission catalogue tree (all 8 domains)."""
    return {"data": PERMISSION_CATALOGUE.model_dump(), "mode": "catalogue"}


@router.get("/domains")
async def list_domains() -> dict[str, object]:
    """List all permission domains with summary counts."""
    summaries: list[dict[str, object]] = []
    for domain_node in PERMISSION_CATALOGUE.domains:
        perm_count = sum(len(cat.permissions) for cat in domain_node.categories)
        summaries.append(
            {
                "domain": domain_node.domain.value,
                "label": domain_node.label,
                "description": domain_node.description,
                "category_count": len(domain_node.categories),
                "permission_count": perm_count,
            }
        )
    return {"data": summaries, "mode": "catalogue"}


@router.get("/domain/{domain}")
async def get_domain(domain: str) -> dict[str, object]:
    """Return a single domain's category and permission tree."""
    # Validate domain value
    try:
        domain_enum = PermissionDomain(domain)
    except ValueError as err:
        valid = [d.value for d in PermissionDomain]
        raise HTTPException(
            status_code=404,
            detail=f"Domain '{domain}' not found. Valid domains: {valid}",
        ) from err

    for domain_node in PERMISSION_CATALOGUE.domains:
        if domain_node.domain == domain_enum:
            return {"data": domain_node.model_dump(), "mode": "catalogue"}

    raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")


@router.get("/search")
async def search_permissions(
    q: str = Query(
        ..., min_length=1, description="Search query (case-insensitive substring match)"
    ),
) -> dict[str, object]:
    """Search permissions by key, label, or description."""
    query_lower = q.lower()
    results: list[dict[str, object]] = []

    for domain_node in PERMISSION_CATALOGUE.domains:
        for cat in domain_node.categories:
            for perm in cat.permissions:
                if (
                    query_lower in perm.key.lower()
                    or query_lower in perm.label.lower()
                    or query_lower in perm.description.lower()
                ):
                    results.append(
                        {
                            **perm.model_dump(),
                            "domain_label": domain_node.label,
                            "category_label": cat.label,
                        }
                    )

    return {
        "data": results,
        "query": q,
        "count": len(results),
        "mode": "catalogue",
    }
