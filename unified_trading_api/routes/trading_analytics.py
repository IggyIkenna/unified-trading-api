"""Trading analytics — PnL, timeseries, performance, organizations, settlements."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from unified_api_contracts.strategy import (  # noqa: qg-deep-import — UAC internal facade
    STRATEGY_REGISTRY,  # noqa: qg-deep-import — UAC internal facade
)

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package
from unified_trading_api.services.period_aggregation import (  # noqa: qg-deep-import — self-package
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
    strategy_id: str = Query(None, description="Filter PnL rows by strategy ID"),
    period: str = Query("1d"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get PnL breakdown with live/batch mode support."""
    service = get_service(request)
    collection = f"pnl_{mode}"
    records = service.list(
        collection, filters={"venue": venue, "strategy_id": strategy_id, "as_of": as_of}
    )
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
    asset_group: str = Query(None),
) -> dict[str, object]:
    """Get analytics instrument list."""
    service = get_service(request)
    records = service.list("analytics_instruments", filters={"asset_group": asset_group})
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
    asset_group: str = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get all strategy configs with filtering."""
    service = get_service(request)
    records = service.list("strategies", filters={"asset_group": asset_group, "status": status})
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


@router.get("/strategies/catalog")
async def get_strategy_catalog(
    request: Request,
    domain: str = Query(None, description="Filter by domain: defi, cefi, tradfi, sports"),
) -> dict[str, object]:
    """Return the full strategy catalog from UAC StrategyRegistry (SSOT).

    This powers the UI strategy family browser — traders can see every available
    strategy type, its domain, family, and configurable parameters at a glance.
    Data sourced from the UAC StrategyRegistry singleton.
    """
    registry_data = STRATEGY_REGISTRY.to_dict()
    raw_strategies: list[dict[str, object]] = registry_data.get("strategies", [])  # type: ignore[assignment]
    catalog: list[dict[str, object]] = [
        {
            "id": s["strategy_id"],
            "domain": str(s["asset_group"]).lower(),
            "family": str(s["family"]).lower().replace("_", "-"),
            "label": s["name"],
            "params": [],
        }
        for s in raw_strategies
    ]
    # Also include supplementary entries for strategies not yet in the UAC registry
    _registry_ids = {s["id"] for s in catalog}
    _supplementary: list[dict[str, object]] = [
        {
            "id": "AAVE_LENDING",
            "domain": "defi",
            "family": "lending",
            "label": "Aave V3 Lending",
            "params": ["token", "chain", "target_utilization"],
        },
        {
            "id": "ETH_LENDING",
            "domain": "defi",
            "family": "lending",
            "label": "ETH Lending Yield",
            "params": ["protocol", "target_apy_floor"],
        },
        {
            "id": "BTC_LENDING",
            "domain": "defi",
            "family": "lending",
            "label": "BTC Lending Yield",
            "params": ["protocol", "target_apy_floor"],
        },
        {
            "id": "SOL_LENDING",
            "domain": "defi",
            "family": "lending",
            "label": "SOL Kamino Lending",
            "params": ["protocol", "target_apy_floor"],
        },
        {
            "id": "MULTICHAIN_LENDING",
            "domain": "defi",
            "family": "lending",
            "label": "Multi-Chain Lending",
            "params": ["chains", "protocols", "rebalance_threshold_bps"],
        },
        {
            "id": "LENDING_PROTOCOL_ARB",
            "domain": "defi",
            "family": "lending-arb",
            "label": "Lending Protocol Arb",
            "params": ["protocols", "min_spread_bps", "max_position_usd"],
        },
        {
            "id": "LENDING_PROTOCOL_ARB_ETH",
            "domain": "defi",
            "family": "lending-arb",
            "label": "Lending Arb (ETH)",
            "params": ["protocols", "min_spread_bps"],
        },
        {
            "id": "LENDING_PROTOCOL_ARB_ARB",
            "domain": "defi",
            "family": "lending-arb",
            "label": "Lending Arb (Arbitrum)",
            "params": ["protocols", "min_spread_bps"],
        },
        {
            "id": "BASIS_TRADE",
            "domain": "defi",
            "family": "basis",
            "label": "ETH Basis Trade",
            "params": ["funding_threshold_bps", "hedge_ratio", "rebalance_interval_h"],
        },
        {
            "id": "STAKED_BASIS",
            "domain": "defi",
            "family": "basis",
            "label": "Staked Basis Trade",
            "params": ["lst_token", "funding_threshold_bps", "stake_protocol"],
        },
        {
            "id": "RECURSIVE_STAKED_BASIS",
            "domain": "defi",
            "family": "basis",
            "label": "Recursive Staked Basis",
            "params": ["max_leverage", "health_floor", "lst_token"],
        },
        {
            "id": "BTC_BASIS",
            "domain": "defi",
            "family": "basis",
            "label": "BTC Basis Trade",
            "params": ["funding_threshold_bps", "hedge_ratio"],
        },
        {
            "id": "SOL_BASIS",
            "domain": "defi",
            "family": "basis",
            "label": "SOL Basis Trade",
            "params": ["funding_threshold_bps", "hedge_ratio"],
        },
        {
            "id": "SOL_STAKED_BASIS",
            "domain": "defi",
            "family": "basis",
            "label": "SOL Staked Basis",
            "params": ["lst_token", "stake_protocol"],
        },
        {
            "id": "L2_BASIS",
            "domain": "defi",
            "family": "basis",
            "label": "L2 Basis Trade",
            "params": ["l2_chain", "bridge_protocol"],
        },
        {
            "id": "ENHANCED_BASIS_MULTI_VENUE",
            "domain": "defi",
            "family": "basis",
            "label": "Enhanced Basis (Multi-Venue)",
            "params": ["venues", "min_spread_bps"],
        },
        {
            "id": "ENHANCED_BASIS_MULTI_COIN",
            "domain": "defi",
            "family": "basis",
            "label": "Enhanced Basis (Multi-Coin)",
            "params": ["coins", "correlation_threshold"],
        },
        {
            "id": "UNHEDGED_RECURSIVE",
            "domain": "defi",
            "family": "recursive",
            "label": "Unhedged Recursive",
            "params": ["max_leverage", "health_floor"],
        },
        {
            "id": "ETHENA_BENCHMARK",
            "domain": "defi",
            "family": "benchmark",
            "label": "Ethena Benchmark",
            "params": ["benchmark_apy", "rebalance_threshold"],
        },
        {
            "id": "CROSS_CHAIN_YIELD_ARB",
            "domain": "defi",
            "family": "cross-chain",
            "label": "Cross-Chain Yield Arb",
            "params": ["chains", "min_yield_diff_bps"],
        },
        {
            "id": "CROSS_CHAIN_SOR",
            "domain": "defi",
            "family": "cross-chain",
            "label": "Cross-Chain SOR Rebalancing",
            "params": ["chains", "rebalance_threshold_pct"],
        },
        {
            "id": "OMNICHAIN_TRANSFER",
            "domain": "defi",
            "family": "cross-chain",
            "label": "Omnichain Transfer",
            "params": ["source_chain", "dest_chain", "bridge_protocol"],
        },
        {
            "id": "ACTIVE_LP_ETH_USDC",
            "domain": "defi",
            "family": "lp",
            "label": "Active LP ETH/USDC",
            "params": ["range_width_pct", "rebalance_trigger_pct", "venue"],
        },
        {
            "id": "ACTIVE_LP_SOL_USDC",
            "domain": "defi",
            "family": "lp",
            "label": "Active LP SOL/USDC",
            "params": ["range_width_pct", "rebalance_trigger_pct", "venue"],
        },
        {
            "id": "SOL_CONCENTRATED_LP",
            "domain": "defi",
            "family": "lp",
            "label": "SOL Concentrated LP",
            "params": ["range_width_pct", "fee_tier"],
        },
        {
            "id": "AMM_LP",
            "domain": "defi",
            "family": "lp",
            "label": "AMM LP",
            "params": ["pool", "fee_tier"],
        },
        {
            "id": "LIQUIDATION_CAPTURE",
            "domain": "defi",
            "family": "liquidation",
            "label": "Liquidation Cascade Capture",
            "params": ["min_profit_usd", "max_gas_gwei", "protocols"],
        },
        {
            "id": "BTC_MOMENTUM",
            "domain": "cefi",
            "family": "momentum",
            "label": "BTC Momentum",
            "params": ["lookback_days", "signal_threshold", "position_size_pct"],
        },
        {
            "id": "ETH_MOMENTUM",
            "domain": "cefi",
            "family": "momentum",
            "label": "ETH Momentum",
            "params": ["lookback_days", "signal_threshold", "position_size_pct"],
        },
        {
            "id": "SOL_MOMENTUM",
            "domain": "cefi",
            "family": "momentum",
            "label": "SOL Momentum",
            "params": ["lookback_days", "signal_threshold", "position_size_pct"],
        },
        {
            "id": "BTC_MEAN_REVERSION",
            "domain": "cefi",
            "family": "mean-reversion",
            "label": "BTC Mean Reversion",
            "params": ["z_score_entry", "z_score_exit", "lookback_days"],
        },
        {
            "id": "ETH_MEAN_REVERSION",
            "domain": "cefi",
            "family": "mean-reversion",
            "label": "ETH Mean Reversion",
            "params": ["z_score_entry", "z_score_exit", "lookback_days"],
        },
        {
            "id": "SOL_MEAN_REVERSION",
            "domain": "cefi",
            "family": "mean-reversion",
            "label": "SOL Mean Reversion",
            "params": ["z_score_entry", "z_score_exit", "lookback_days"],
        },
        {
            "id": "BTC_ML_DIRECTIONAL",
            "domain": "cefi",
            "family": "ml-directional",
            "label": "BTC ML Directional",
            "params": ["model_id", "confidence_threshold", "retrain_interval_h"],
        },
        {
            "id": "ETH_ML_DIRECTIONAL",
            "domain": "cefi",
            "family": "ml-directional",
            "label": "ETH ML Directional",
            "params": ["model_id", "confidence_threshold"],
        },
        {
            "id": "SOL_ML_DIRECTIONAL",
            "domain": "cefi",
            "family": "ml-directional",
            "label": "SOL ML Directional",
            "params": ["model_id", "confidence_threshold"],
        },
        {
            "id": "BTC_MARKET_MAKING",
            "domain": "cefi",
            "family": "market-making",
            "label": "BTC Market Making",
            "params": ["spread_bps", "inventory_skew", "venues"],
        },
        {
            "id": "ETH_MARKET_MAKING",
            "domain": "cefi",
            "family": "market-making",
            "label": "ETH Market Making",
            "params": ["spread_bps", "inventory_skew", "venues"],
        },
        {
            "id": "CROSS_EXCHANGE_BTC",
            "domain": "cefi",
            "family": "cross-exchange",
            "label": "Cross-Exchange BTC Arb",
            "params": ["venues", "min_spread_bps", "transfer_time_s"],
        },
        {
            "id": "STAT_ARB_BTC_ETH",
            "domain": "cefi",
            "family": "stat-arb",
            "label": "Stat Arb BTC/ETH",
            "params": ["lookback_days", "z_score_entry", "hedge_ratio"],
        },
        {
            "id": "REL_VOL_BTC_ETH",
            "domain": "cefi",
            "family": "relative-vol",
            "label": "Relative Vol BTC/ETH",
            "params": ["vol_lookback", "entry_threshold", "hedge_instrument"],
        },
        {
            "id": "VOL_SURFACE_BTC",
            "domain": "cefi",
            "family": "vol-surface",
            "label": "BTC Vol Surface Arb",
            "params": ["expiry_range_days", "strike_width", "min_edge_vol_pts"],
        },
        {
            "id": "BTC_OPTIONS_MM",
            "domain": "cefi",
            "family": "options-mm",
            "label": "BTC Options Market Making",
            "params": ["delta_range", "gamma_limit", "venues"],
        },
        {
            "id": "ETH_OPTIONS_MM",
            "domain": "cefi",
            "family": "options-mm",
            "label": "ETH Options Market Making",
            "params": ["delta_range", "gamma_limit", "venues"],
        },
        {
            "id": "BTC_OPTIONS_ML",
            "domain": "cefi",
            "family": "options-ml",
            "label": "BTC Options ML Strike Selection",
            "params": ["model_id", "min_edge_pct", "max_dte"],
        },
        {
            "id": "PREDICTION_ARB_BTC",
            "domain": "cefi",
            "family": "prediction",
            "label": "Prediction Market Arb",
            "params": ["venues", "min_edge_pct", "max_position_usd"],
        },
        {
            "id": "EVENT_MACRO_CRYPTO",
            "domain": "cefi",
            "family": "event-driven",
            "label": "Event-Driven Macro (Crypto)",
            "params": ["event_types", "position_hold_hours"],
        },
        {
            "id": "OIL_COMMODITY_REGIME",
            "domain": "tradfi",
            "family": "commodity-regime",
            "label": "Oil Commodity Regime",
            "params": ["regime_model", "factor_weights", "rebalance_frequency"],
        },
        {
            "id": "NG_COMMODITY_REGIME",
            "domain": "tradfi",
            "family": "commodity-regime",
            "label": "Natural Gas Commodity Regime",
            "params": ["regime_model", "factor_weights"],
        },
        {
            "id": "SPY_MOMENTUM",
            "domain": "tradfi",
            "family": "momentum",
            "label": "SPY Momentum",
            "params": ["lookback_days", "signal_threshold"],
        },
        {
            "id": "SPY_ML_DIRECTIONAL",
            "domain": "tradfi",
            "family": "ml-directional",
            "label": "SPY ML Directional",
            "params": ["model_id", "confidence_threshold"],
        },
        {
            "id": "FX_ML_DIRECTIONAL",
            "domain": "tradfi",
            "family": "ml-directional",
            "label": "FX ML Directional",
            "params": ["model_id", "pair"],
        },
        {
            "id": "OIL_ML_DIRECTIONAL",
            "domain": "tradfi",
            "family": "ml-directional",
            "label": "Oil ML Directional",
            "params": ["model_id", "contract"],
        },
        {
            "id": "SPY_OPTIONS_ML",
            "domain": "tradfi",
            "family": "options-ml",
            "label": "SPY Options ML",
            "params": ["model_id", "min_edge_pct"],
        },
        {
            "id": "ETH_OPTIONS_ML",
            "domain": "tradfi",
            "family": "options-ml",
            "label": "ETH Vol ML",
            "params": ["model_id", "vol_target"],
        },
        {
            "id": "SPY_MEAN_REVERSION",
            "domain": "tradfi",
            "family": "mean-reversion",
            "label": "SPY Mean Reversion",
            "params": ["z_score_entry", "z_score_exit"],
        },
        {
            "id": "FX_MEAN_REVERSION",
            "domain": "tradfi",
            "family": "mean-reversion",
            "label": "FX Mean Reversion",
            "params": ["z_score_entry", "pair"],
        },
        {
            "id": "OIL_MEAN_REVERSION",
            "domain": "tradfi",
            "family": "mean-reversion",
            "label": "Oil Mean Reversion",
            "params": ["z_score_entry", "contract"],
        },
        {
            "id": "EVENT_MACRO_TRADFI",
            "domain": "tradfi",
            "family": "event-driven",
            "label": "Event-Driven Macro (TradFi)",
            "params": ["event_types", "instruments"],
        },
        {
            "id": "SPORTS_ARBITRAGE",
            "domain": "sports",
            "family": "arbitrage",
            "label": "Sports Arbitrage",
            "params": ["venues", "min_edge_pct", "max_stake"],
        },
        {
            "id": "SPORTS_VALUE_BETTING",
            "domain": "sports",
            "family": "value-betting",
            "label": "Sports Value Betting",
            "params": ["model_id", "min_edge_pct", "kelly_fraction"],
        },
        {
            "id": "SPORTS_KELLY",
            "domain": "sports",
            "family": "kelly",
            "label": "Sports Kelly Criterion",
            "params": ["bankroll_pct", "max_bet_fraction"],
        },
        {
            "id": "SPORTS_ML",
            "domain": "sports",
            "family": "ml-sports",
            "label": "Sports ML Predictions",
            "params": ["model_id", "leagues", "confidence_threshold"],
        },
        {
            "id": "SPORTS_HALFTIME_ML",
            "domain": "sports",
            "family": "halftime-ml",
            "label": "Halftime ML Live Betting",
            "params": ["model_id", "min_edge_pct"],
        },
        {
            "id": "SPORTS_MARKET_MAKING",
            "domain": "sports",
            "family": "market-making",
            "label": "Sports Market Making",
            "params": ["spread_pct", "max_exposure"],
        },
    ]
    for legacy in _supplementary:
        if legacy["id"] not in _registry_ids:
            catalog.append(legacy)

    if domain:
        catalog = [s for s in catalog if s["domain"] == domain.lower()]

    families: dict[str, list[dict[str, object]]] = {}
    for entry in catalog:
        fam = str(entry["family"])
        families.setdefault(fam, []).append(entry)

    return single_response(
        {"strategies": catalog, "families": families, "total": len(catalog)},
        domain=domain,
    )
