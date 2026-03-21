"""Risk domain — limits, VaR, greeks, stress tests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RiskLimitsResponse(BaseModel):
    limits: list[dict[str, str | float | int | bool]]


class VaRResponse(BaseModel):
    confidence: float
    horizon: str
    var: list[dict[str, str | float | int]]


class GreeksResponse(BaseModel):
    greeks: list[dict[str, str | float | int]]


class StressTestsResponse(BaseModel):
    stress_tests: list[dict[str, str | float | int]]


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/limits", response_model=RiskLimitsResponse | ErrorResponse)
async def get_risk_limits(
    request: Request,
    venue: str = Query(None),
) -> RiskLimitsResponse | ErrorResponse:
    """Get risk limits."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("risk_limits")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        return RiskLimitsResponse(limits=records)
    return ErrorResponse(error="real mode not yet wired")


@router.get("/var", response_model=VaRResponse | ErrorResponse)
async def get_var(
    request: Request,
    confidence: float = Query(0.99),
    horizon: str = Query("1d"),
) -> VaRResponse | ErrorResponse:
    """Get Value-at-Risk calculations."""
    if getattr(request.app.state, "mock_mode", True):
        return VaRResponse(
            confidence=confidence,
            horizon=horizon,
            var=mock_store.list("var"),
        )
    return ErrorResponse(error="real mode not yet wired")


@router.get("/greeks", response_model=GreeksResponse | ErrorResponse)
async def get_greeks(
    request: Request,
    instrument: str = Query(None),
) -> GreeksResponse | ErrorResponse:
    """Get portfolio greeks."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("greeks")
        if instrument:
            records = [r for r in records if r.get("instrument") == instrument]
        return GreeksResponse(greeks=records)
    return ErrorResponse(error="real mode not yet wired")


@router.get("/stress", response_model=StressTestsResponse | ErrorResponse)
async def get_stress_tests(
    request: Request,
) -> StressTestsResponse | ErrorResponse:
    """Get stress test results."""
    if getattr(request.app.state, "mock_mode", True):
        return StressTestsResponse(stress_tests=mock_store.list("stress_tests"))
    return ErrorResponse(error="real mode not yet wired")
