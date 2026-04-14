"""Trading analytics — PnL, timeseries, performance, organizations, settlements."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginated_response, single_response
from unified_trading_api.services.factory import get_service
from unified_trading_api.services.period_aggregation import (
    compute_multi_period_summary,
    compute_period_changes,
)

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
    records = service.list(collection, filters={"venue": venue, "as_of": as_of})
    return paginated_response(records, page, page_size, mode=mode, as_of=as_of, period=period)


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
    records = service.list(collection, filters={"as_of": as_of})
    return paginated_response(
        records,
        page,
        page_size,
        mode=mode,
        as_of=as_of,
        metric=metric,
        period=period,
        granularity=granularity,
    )


@router.get("/performance")
async def get_performance(
    request: Request,
    period: str = Query("30d"),
) -> dict[str, object]:
    """Get performance metrics."""
    service = get_service(request)
    return single_response(service.list("performance"), period=period)


@router.get("/organizations")
async def get_organizations(
    request: Request,
) -> dict[str, object]:
    """Get analytics organizations."""
    service = get_service(request)
    return single_response(service.list("analytics_organizations"))


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
    return paginated_response(records, page, page_size)


@router.get("/instruments")
async def get_instruments(
    request: Request,
    asset_class: str = Query(None),
) -> dict[str, object]:
    """Get analytics instrument list."""
    service = get_service(request)
    records = service.list("analytics_instruments", filters={"asset_class": asset_class})
    return single_response(records)


# -- POST endpoints ---------------------------------------------------------


@router.post("/pnl")
async def create_pnl_snapshot(
    request: Request,
) -> dict[str, object]:
    """Trigger a PnL snapshot calculation."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("pnl", body)
    return single_response({"record": record, "status": "created"})


@router.post("/timeseries")
async def create_timeseries_entry(
    request: Request,
) -> dict[str, object]:
    """Add a timeseries data point."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("analytics_timeseries", body)
    return single_response({"record": record, "status": "created"})


@router.post("/performance")
async def create_performance_snapshot(
    request: Request,
) -> dict[str, object]:
    """Trigger a performance snapshot."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("performance", body)
    return single_response({"record": record, "status": "created"})


@router.post("/settlements")
async def create_settlement(
    request: Request,
) -> dict[str, object]:
    """Create a settlement record."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("settlements", body)
    return single_response({"record": record, "status": "created"})


# -- Period aggregation endpoints --------------------------------------------


@router.get("/period-changes")
async def get_period_changes(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    period: str = Query("1d", description="1d, wtd, mtd, qtd, ytd, 7d, 30d, 90d, 365d"),
    metric: str = Query("pnl", description="pnl, equity, risk, exposure"),
    as_of: str = Query(None, description="Reference date (YYYY-MM-DD UTC). Defaults to today."),
) -> dict[str, object]:
    """Compute period-over-period changes for a metric from daily snapshots.

    Returns absolute and percentage changes between period start and the as_of date.
    All dates are UTC midnight boundaries.
    """
    service = get_service(request)
    collection = f"pnl_timeseries_{mode}"
    snapshots: list[dict[str, object]] = service.list(collection)

    ref_date = date.fromisoformat(as_of) if as_of else None

    # Metric → numeric fields mapping
    field_map: dict[str, list[str]] = {
        "pnl": ["total_pnl", "realized_pnl", "unrealized_pnl", "funding_pnl"],
        "equity": ["account_equity", "total_position_value", "cash_balance"],
        "risk": ["leverage", "concentration", "drawdown", "health_factor"],
        "exposure": ["gross_exposure", "net_exposure", "long_exposure", "short_exposure"],
    }
    fields = field_map.get(metric, field_map["pnl"])

    result = compute_period_changes(
        snapshots,
        period,
        fields,
        as_of=ref_date,
    )
    return single_response(result, mode=mode, metric=metric)


@router.get("/period-summary")
async def get_period_summary(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    metric: str = Query("pnl"),
    as_of: str = Query(None, description="Reference date (YYYY-MM-DD UTC). Defaults to today."),
) -> dict[str, object]:
    """Compute changes across all standard periods (1d, wtd, mtd, qtd, ytd).

    Returns a dict of period → changes for the UI dashboard cards.
    """
    service = get_service(request)
    collection = f"pnl_timeseries_{mode}"
    snapshots: list[dict[str, object]] = service.list(collection)

    ref_date = date.fromisoformat(as_of) if as_of else None

    field_map: dict[str, list[str]] = {
        "pnl": ["total_pnl", "realized_pnl", "unrealized_pnl", "funding_pnl"],
        "equity": ["account_equity", "total_position_value", "cash_balance"],
        "risk": ["leverage", "concentration", "drawdown", "health_factor"],
        "exposure": ["gross_exposure", "net_exposure", "long_exposure", "short_exposure"],
    }
    fields = field_map.get(metric, field_map["pnl"])

    summary = compute_multi_period_summary(
        snapshots,
        fields,
        as_of=ref_date,
    )
    return single_response({"periods": summary}, mode=mode, metric=metric)


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
    return paginated_response(records, page, page_size)


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
    return single_response(strategy)


@router.post("/strategies/{strategy_id}/promote")
async def promote_strategy(
    request: Request,
    strategy_id: str,
) -> dict[str, object]:
    """Promote a strategy from staging to live."""
    service = get_service(request)
    updated = service.update("strategies", strategy_id, {"status": "live"})
    if updated:
        return single_response({"strategy": updated, "status": "promoted"})
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
        return single_response({"strategy": updated, "status": "rejected"})
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
        return single_response(
            {"strategy": updated, "status": "scaled", "scale_factor": scale_factor}
        )
    return {"error": {"code": "NOT_FOUND", "message": f"Strategy {strategy_id} not found"}}


@router.get("/live-batch-delta")
async def get_live_batch_delta(
    request: Request,
    metric: str = Query("pnl", description="pnl, equity, exposure"),
    as_of: str = Query(None, description="Reference date (YYYY-MM-DD UTC). Defaults to today."),
) -> dict[str, object]:
    """Reconciliation view comparing live vs batch values for a metric.

    Returns per-field deltas (live_value, batch_value, absolute_diff, pct_diff)
    so ops can spot divergence between real-time and T+1 numbers.
    """
    service = get_service(request)
    live_records: list[dict[str, object]] = service.list("pnl_timeseries_live")
    batch_records: list[dict[str, object]] = service.list("pnl_timeseries_batch")

    field_map: dict[str, list[str]] = {
        "pnl": ["total_pnl", "realized_pnl", "unrealized_pnl", "funding_pnl"],
        "equity": ["account_equity", "total_position_value", "cash_balance"],
        "exposure": ["gross_exposure", "net_exposure", "long_exposure", "short_exposure"],
    }
    fields = field_map.get(metric, field_map["pnl"])

    # Build last-snapshot comparison
    deltas: list[dict[str, object]] = []
    live_last = live_records[-1] if live_records else {}
    batch_last = batch_records[-1] if batch_records else {}
    for field in fields:
        live_val = float(live_last.get(field, 0) or 0)
        batch_val = float(batch_last.get(field, 0) or 0)
        abs_diff = round(live_val - batch_val, 4)
        pct_diff = round(abs_diff / batch_val * 100, 4) if batch_val else 0.0
        deltas.append(
            {
                "field": field,
                "live_value": live_val,
                "batch_value": batch_val,
                "absolute_diff": abs_diff,
                "pct_diff": pct_diff,
            }
        )

    return single_response(
        {"deltas": deltas, "metric": metric, "as_of": as_of},
    )


@router.get("/strategy-configs")
async def get_strategy_configs(
    request: Request,
) -> dict[str, object]:
    """Get all strategy configs for UI consumption."""
    service = get_service(request)
    return single_response(service.list("strategies"))
