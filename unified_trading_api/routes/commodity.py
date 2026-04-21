"""Commodity regime trading — HMM regime detection, factor decomposition, COT positioning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    single_response,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/regime-state")
async def get_regime_state(request: Request) -> dict[str, object]:
    """Current HMM regime state with confidence and transition metadata."""
    service = get_service(request)
    records = service.list("commodity_regime_state")
    if records:
        return single_response(records[0])
    return single_response(
        {
            "regime": "UNKNOWN",
            "confidence": 0.0,
            "updatedAt": "",
            "priorRegime": "UNKNOWN",
            "transitionTimestamp": "",
            "hmm_log_likelihood": 0.0,
        }
    )


@router.get("/factors")
async def get_factors(request: Request) -> dict[str, object]:
    """Factor decomposition — 5 fundamental commodity factors with weights and values."""
    service = get_service(request)
    records = service.list("commodity_factors")
    return single_response(records)


@router.get("/cot-positioning")
async def get_cot_positioning(request: Request) -> dict[str, object]:
    """CFTC COT positioning time series — speculative vs commercial net positions."""
    service = get_service(request)
    records = service.list("commodity_cot_positioning")
    return single_response(records)


@router.get("/regime-history")
async def get_regime_history(request: Request) -> dict[str, object]:
    """Regime transition history over last 90 days."""
    service = get_service(request)
    records = service.list("commodity_regime_history")
    return single_response(records)


@router.get("/positions")
async def get_commodity_positions(request: Request) -> dict[str, object]:
    """Active commodity positions with regime-at-entry metadata."""
    service = get_service(request)
    records = service.list("commodity_positions")
    return single_response(records)
