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
    mode: str = Query("live", pattern="^(live|batch)$"),
    venue: str = Query(None),
    period: str = Query("1d"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get PnL breakdown with live/batch mode support."""
    service = get_service(request)
    collection = f"pnl_{mode}"
    records = service.list(collection, filters={"venue": venue})
    data, pagination = paginate(records, page, page_size)
    return {
        "period": period,
        "data": data,
        "pagination": pagination.model_dump(),
        "mode": mode,
        "as_of": as_of,
    }


@router.get("/timeseries")
async def get_timeseries(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    metric: str = Query("equity"),
    period: str = Query("1d"),
    granularity: str = Query("1h"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get analytics timeseries data with live/batch mode support."""
    service = get_service(request)
    collection = f"pnl_timeseries_{mode}"
    records = service.list(collection)
    data, pagination = paginate(records, page, page_size)
    return {
        "metric": metric,
        "period": period,
        "granularity": granularity,
        "data": data,
        "pagination": pagination.model_dump(),
        "mode": mode,
        "as_of": as_of,
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
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("pnl", body)
    return {"status": "created", "record": record}


@router.post("/timeseries")
async def create_timeseries_entry(
    request: Request,
) -> dict[str, object]:
    """Add a timeseries data point."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("analytics_timeseries", body)
    return {"status": "created", "record": record}


@router.post("/performance")
async def create_performance_snapshot(
    request: Request,
) -> dict[str, object]:
    """Trigger a performance snapshot."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("performance", body)
    return {"status": "created", "record": record}


@router.post("/settlements")
async def create_settlement(
    request: Request,
) -> dict[str, object]:
    """Create a settlement record."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("settlements", body)
    return {"status": "created", "record": record}


# -- Strategy endpoints -----------------------------------------------------


@router.get("/strategies")
async def get_strategies(
    request: Request,
    asset_class: str = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get all strategy configs with filtering."""
    service = get_service(request)
    records = service.list("strategies", filters={"asset_class": asset_class, "status": status})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/strategies/{strategy_id}")
async def get_strategy_detail(
    request: Request,
    strategy_id: str,
) -> dict[str, object]:
    """Get a single strategy detail by ID."""
    service = get_service(request)
    strategy = service.get("strategies", strategy_id)
    if not strategy:
        return {"error": {"code": "NOT_FOUND", "message": f"Strategy {strategy_id} not found"}}
    return {"strategy": strategy}


@router.post("/strategies/{strategy_id}/promote")
async def promote_strategy(
    request: Request,
    strategy_id: str,
) -> dict[str, object]:
    """Promote a strategy from staging to live."""
    service = get_service(request)
    updated = service.update("strategies", strategy_id, {"status": "live"})
    if updated:
        return {"status": "promoted", "strategy": updated}
    return {"error": {"code": "NOT_FOUND", "message": f"Strategy {strategy_id} not found"}}


@router.post("/strategies/{strategy_id}/reject")
async def reject_strategy(
    request: Request,
    strategy_id: str,
) -> dict[str, object]:
    """Reject a strategy."""
    service = get_service(request)
    updated = service.update("strategies", strategy_id, {"status": "rejected"})
    if updated:
        return {"status": "rejected", "strategy": updated}
    return {"error": {"code": "NOT_FOUND", "message": f"Strategy {strategy_id} not found"}}


@router.post("/strategies/{strategy_id}/scale")
async def scale_strategy(
    request: Request,
    strategy_id: str,
) -> dict[str, object]:
    """Scale a strategy's position size."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    scale_factor = float(str(body.get("scale_factor", 1.0)))
    updated = service.update("strategies", strategy_id, {"position_scale": scale_factor})
    if updated:
        return {"status": "scaled", "scale_factor": scale_factor, "strategy": updated}
    return {"error": {"code": "NOT_FOUND", "message": f"Strategy {strategy_id} not found"}}


@router.get("/strategy-configs")
async def get_strategy_configs(
    request: Request,
) -> dict[str, object]:
    """Get all strategy configs for UI consumption."""
    service = get_service(request)
    return {"configs": service.list("strategies")}
