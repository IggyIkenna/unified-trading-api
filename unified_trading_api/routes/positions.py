"""Positions domain — active positions, summary, balances."""

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


@router.get("/active")
async def get_active_positions(
    request: Request,
    venue: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get currently active positions."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("positions")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/summary")
async def get_position_summary(
    request: Request,
) -> dict[str, object]:
    """Get aggregated position summary across venues."""
    if getattr(request.app.state, "mock_mode", True):
        return {"summary": mock_store.list("position_summary")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/balances")
async def get_balances(
    request: Request,
    venue: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get account balances across venues."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("balances")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
