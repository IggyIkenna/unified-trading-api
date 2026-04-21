"""Registry admin endpoints — catalogue lifecycle mutations.

Plan A — strategy_lifecycle_maturity_model_2026_04_21. UAC owns the immutable
catalogue of possible strategy instances (``STRATEGY_INSTANCE_CATALOGUE``);
Firestore owns the mutable lifecycle state (maturity phase, product routing,
series refs) in the ``strategy_instance_lifecycle`` collection. This router
exposes admin-only PATCH endpoints that drive transitions via the
``DomainService`` update contract.

The backing ``LifecycleReloader`` in services hot-reloads this collection on a
5-min cadence and emits ``STRATEGY_LIFECYCLE_CHANGED`` when entries change.

SCHEMA_PROVENANCE_EXEMPT: LifecyclePatchRequest is the HTTP PATCH body — an API
request-shape wrapper over UAC enums (StrategyMaturityPhase / ProductRouting).
The domain contract is the UAC enums themselves; this is the transport wrapper.
"""

# SCHEMA_PROVENANCE_EXEMPT — see module docstring above.

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from unified_api_contracts.internal.domain.strategy_service import (  # noqa: qg-deep-import — UAC internal domain facade
    ProductRouting,
    StrategyMaturityPhase,
    is_valid_maturity_transition,
)

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

_LIFECYCLE_COLLECTION = "strategy_instance_lifecycle"


class LifecyclePatchRequest(BaseModel):  # CORRECT-LOCAL: API registry PATCH request
    """Admin PATCH payload for a strategy-instance lifecycle record."""

    model_config = ConfigDict(extra="forbid")

    maturity_phase: StrategyMaturityPhase | None = Field(
        default=None,
        description="New maturity phase (forward-only ladder; any → retired).",
    )
    product_routing: ProductRouting | None = Field(
        default=None,
        description="New product routing gating customer surfaces.",
    )
    rationale: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional operator rationale stored in phase_history.",
    )


@router.patch("/strategy-instances/{instance_id}/lifecycle")
async def patch_strategy_instance_lifecycle(
    request: Request,
    instance_id: str,
    body: LifecyclePatchRequest,
) -> dict[str, object]:
    """Admin PATCH — transition an instance's maturity phase / product routing.

    Validations:
      - At least one of ``maturity_phase`` / ``product_routing`` must be set.
      - Maturity transitions must be legal per
        ``is_valid_maturity_transition`` (forward-only ladder; ``retired`` is
        terminal; any phase may transition to ``retired``).
      - Existing lifecycle record must exist — the UAC catalogue is the SSOT
        for which ``instance_id`` values are valid; this endpoint does not
        accept arbitrary IDs.

    Returns the updated record, including the appended ``phase_history`` row
    when the maturity phase changed.
    """
    if body.maturity_phase is None and body.product_routing is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of maturity_phase or product_routing is required",
        )

    service = get_service(request)
    existing = service.get(_LIFECYCLE_COLLECTION, instance_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"No lifecycle record for instance_id={instance_id}",
        )

    now = datetime.now(UTC)
    now_iso = now.isoformat()

    update: dict[str, object] = {"phased_at": now_iso}

    if body.maturity_phase is not None:
        prev_value = existing.get("maturity_phase")
        prev_phase = StrategyMaturityPhase(prev_value) if isinstance(prev_value, str) else None
        if prev_phase is not None and not is_valid_maturity_transition(
            prev_phase, body.maturity_phase
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Illegal maturity transition {prev_phase.value} -> {body.maturity_phase.value}"
                ),
            )
        update["maturity_phase"] = body.maturity_phase.value
        history_raw = existing.get("phase_history")
        history: list[dict[str, object]] = (
            list(history_raw) if isinstance(history_raw, list) else []
        )
        history.append(
            {
                "from_phase": prev_phase.value if prev_phase is not None else None,
                "to_phase": body.maturity_phase.value,
                "transitioned_at_utc": now_iso,
                "transitioned_by": "admin",
                "rationale": body.rationale or "",
            }
        )
        update["phase_history"] = history

    if body.product_routing is not None:
        update["product_routing"] = body.product_routing.value

    updated = service.update(_LIFECYCLE_COLLECTION, instance_id, update)
    if updated is None:
        raise HTTPException(status_code=500, detail="Lifecycle update returned no record")

    logger.info(
        "PATCH /registry/strategy-instances/%s/lifecycle maturity=%s routing=%s",
        instance_id,
        body.maturity_phase.value if body.maturity_phase else None,
        body.product_routing.value if body.product_routing else None,
    )
    return {"data": updated}
