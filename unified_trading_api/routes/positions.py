"""Positions domain — active positions, summary, balances."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PositionsResponse(BaseModel):
    positions: list[dict[str, float | str | int | bool]]


class PositionSummaryResponse(BaseModel):
    summary: list[dict[str, float | str | int]]


class BalancesResponse(BaseModel):
    balances: list[dict[str, float | str | int]]


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/active", response_model=PositionsResponse | ErrorResponse)
async def get_active_positions(
    request: Request,
    venue: str = Query(None),
) -> PositionsResponse | ErrorResponse:
    """Get currently active positions."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("positions")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        return PositionsResponse(positions=records)
    return ErrorResponse(error="real mode not yet wired")


@router.get("/summary", response_model=PositionSummaryResponse | ErrorResponse)
async def get_position_summary(
    request: Request,
) -> PositionSummaryResponse | ErrorResponse:
    """Get aggregated position summary across venues."""
    if getattr(request.app.state, "mock_mode", True):
        return PositionSummaryResponse(summary=mock_store.list("position_summary"))
    return ErrorResponse(error="real mode not yet wired")


@router.get("/balances", response_model=BalancesResponse | ErrorResponse)
async def get_balances(
    request: Request,
    venue: str = Query(None),
) -> BalancesResponse | ErrorResponse:
    """Get account balances across venues."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("balances")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        return BalancesResponse(balances=records)
    return ErrorResponse(error="real mode not yet wired")
