"""Risk domain — limits, VaR, greeks, stress tests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/limits")
async def get_risk_limits(
    request: Request,
    venue: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get risk limits."""
    service = get_service(request)
    records = service.list("risk_limits", filters={"venue": venue})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/var")
async def get_var(
    request: Request,
    confidence: float = Query(0.99),
    horizon: str = Query("1d"),
) -> dict[str, object]:
    """Get Value-at-Risk calculations."""
    service = get_service(request)
    return {
        "confidence": confidence,
        "horizon": horizon,
        "var": service.list("var"),
    }


@router.get("/greeks")
async def get_greeks(
    request: Request,
    instrument: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get portfolio greeks."""
    service = get_service(request)
    records = service.list("greeks", filters={"instrument": instrument})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/stress")
async def get_stress_tests(
    request: Request,
) -> dict[str, object]:
    """Get stress test results."""
    service = get_service(request)
    return {"stress_tests": service.list("stress_tests")}
