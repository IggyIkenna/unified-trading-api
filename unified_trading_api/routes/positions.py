"""Positions domain — active positions, summary, balances."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/active")
async def get_active_positions(
    request: Request,
    venue: str = Query(None),
    strategy_id: str = Query(None),
    mode: str = Query("live", pattern="^(live|batch)$"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get currently active positions with live/batch mode."""
    service = get_service(request)
    collection = f"positions_{mode}"
    records = service.list(collection, filters={"venue": venue, "strategy_id": strategy_id})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump(), "mode": mode, "as_of": as_of}


@router.get("/summary")
async def get_position_summary(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
) -> dict[str, object]:
    """Get aggregated position summary across venues."""
    service = get_service(request)
    return {"mode": mode, "summary": service.list("position_summary")}


@router.get("/balances")
async def get_balances(
    request: Request,
    venue: str = Query(None),
    mode: str = Query("live", pattern="^(live|batch)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get account balances across venues."""
    service = get_service(request)
    records = service.list("balances", filters={"venue": venue})
    data, pagination = paginate(records, page, page_size)
    return {"mode": mode, "data": data, "pagination": pagination.model_dump()}
