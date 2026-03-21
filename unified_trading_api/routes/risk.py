"""Risk domain — limits, VaR, greeks, stress tests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store
from unified_trading_api.models.standard import (
    ErrorDetail,
    StandardErrorResponse,
    paginate,
)

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
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("risk_limits")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/var")
async def get_var(
    request: Request,
    confidence: float = Query(0.99),
    horizon: str = Query("1d"),
) -> dict[str, object]:
    """Get Value-at-Risk calculations."""
    if getattr(request.app.state, "mock_mode", True):
        return {
            "confidence": confidence,
            "horizon": horizon,
            "var": mock_store.list("var"),
        }
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/greeks")
async def get_greeks(
    request: Request,
    instrument: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get portfolio greeks."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("greeks")
        if instrument:
            records = [r for r in records if r.get("instrument") == instrument]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/stress")
async def get_stress_tests(
    request: Request,
) -> dict[str, object]:
    """Get stress test results."""
    if getattr(request.app.state, "mock_mode", True):
        return {"stress_tests": mock_store.list("stress_tests")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
