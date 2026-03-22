"""Trading analytics — PnL, timeseries, performance, organizations, settlements."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


# -- GET endpoints ----------------------------------------------------------


@router.get("/pnl")
async def get_pnl(
    request: Request,
    venue: str = Query(None),
    period: str = Query("1d"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get PnL breakdown."""
    service = get_service(request)
    records = service.list("pnl", filters={"venue": venue})
    data, pagination = paginate(records, page, page_size)
    return {"period": period, "data": data, "pagination": pagination.model_dump()}


@router.get("/timeseries")
async def get_timeseries(
    request: Request,
    metric: str = Query("equity"),
    period: str = Query("1d"),
    granularity: str = Query("1h"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get analytics timeseries data."""
    service = get_service(request)
    records = service.list("analytics_timeseries")
    data, pagination = paginate(records, page, page_size)
    return {
        "metric": metric,
        "period": period,
        "granularity": granularity,
        "data": data,
        "pagination": pagination.model_dump(),
    }


@router.get("/performance")
async def get_performance(
    request: Request,
    period: str = Query("30d"),
) -> dict[str, object]:
    """Get performance metrics."""
    service = get_service(request)
    return {"period": period, "performance": service.list("performance")}


@router.get("/organizations")
async def get_organizations(
    request: Request,
) -> dict[str, object]:
    """Get analytics organizations."""
    service = get_service(request)
    return {"organizations": service.list("analytics_organizations")}


@router.get("/settlements")
async def get_settlements(
    request: Request,
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get settlement records."""
    service = get_service(request)
    records = service.list("settlements", filters={"status": status})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/instruments")
async def get_instruments(
    request: Request,
    asset_class: str = Query(None),
) -> dict[str, object]:
    """Get analytics instrument list."""
    service = get_service(request)
    records = service.list("analytics_instruments", filters={"asset_class": asset_class})
    return {"instruments": records}


# -- POST endpoints ---------------------------------------------------------


@router.post("/pnl")
async def create_pnl_snapshot(
    request: Request,
) -> dict[str, object]:
    """Trigger a PnL snapshot calculation."""
    service = get_service(request)
    body = await request.json()
    record = service.create("pnl", body)
    return {"status": "created", "record": record}


@router.post("/timeseries")
async def create_timeseries_entry(
    request: Request,
) -> dict[str, object]:
    """Add a timeseries data point."""
    service = get_service(request)
    body = await request.json()
    record = service.create("analytics_timeseries", body)
    return {"status": "created", "record": record}


@router.post("/performance")
async def create_performance_snapshot(
    request: Request,
) -> dict[str, object]:
    """Trigger a performance snapshot."""
    service = get_service(request)
    body = await request.json()
    record = service.create("performance", body)
    return {"status": "created", "record": record}


@router.post("/settlements")
async def create_settlement(
    request: Request,
) -> dict[str, object]:
    """Create a settlement record."""
    service = get_service(request)
    body = await request.json()
    record = service.create("settlements", body)
    return {"status": "created", "record": record}
