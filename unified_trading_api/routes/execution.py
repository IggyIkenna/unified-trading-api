"""Execution domain — orders, fills, venues, algos, backtests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/orders")
async def get_orders(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    venue: str = Query(None),
    status: str = Query(None),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get orders with live/batch mode support."""
    service = get_service(request)
    collection = f"orders_{mode}"
    records = service.list(collection, filters={"venue": venue, "status": status})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump(), "mode": mode, "as_of": as_of}


@router.get("/fills")
async def get_fills(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    venue: str = Query(None),
    order_id: str = Query(None),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get trade fills with live/batch mode support."""
    service = get_service(request)
    collection = f"fills_{mode}"
    records = service.list(collection, filters={"venue": venue, "order_id": order_id})
    if not records:
        records = service.list("fills", filters={"venue": venue, "order_id": order_id})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump(), "mode": mode, "as_of": as_of}


@router.get("/venues")
async def get_venues(request: Request) -> dict[str, object]:
    """Get configured execution venues."""
    service = get_service(request)
    return {"venues": service.list("execution_venues")}


@router.get("/algos")
async def get_algos(request: Request) -> dict[str, object]:
    """Get available execution algorithms."""
    service = get_service(request)
    return {"algos": service.list("algos")}


@router.get("/backtests")
async def get_backtests(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get backtest runs."""
    service = get_service(request)
    records = service.list("backtests")
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.post("/orders")
async def create_order(
    request: Request,
    body: dict[str, object],
) -> dict[str, object]:
    """Place a new order (mock: persists to store, real: routes to execution-service)."""
    service = get_service(request)
    order = service.create("orders_live", body)
    return {"data": order, "status": "created"}
