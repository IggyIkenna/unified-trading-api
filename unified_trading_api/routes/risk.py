"""Risk domain — limits, VaR, greeks, stress tests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginated_response, single_response
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/exposure")
async def get_risk_exposure(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    strategy_id: str = Query(None),
    category: str = Query(None, description="Filter by category: cefi, defi, tradfi, sports"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
) -> dict[str, object]:
    """Get risk exposure. mode=live for real-time, mode=batch for T+1."""
    service = get_service(request)
    collection = f"risk_{mode}"
    records = service.list(collection, filters={"strategy_id": strategy_id, "category": category})
    return single_response(records, mode=mode, as_of=as_of)


@router.get("/limits")
async def get_risk_limits(
    request: Request,
    venue: str = Query(None),
    mode: str = Query("live", pattern="^(live|batch)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get risk limits."""
    service = get_service(request)
    records = service.list("risk_limits", filters={"venue": venue})
    return paginated_response(records, page, page_size, mode=mode)


@router.get("/var")
async def get_var(
    request: Request,
    confidence: float = Query(0.99),
    horizon: str = Query("1d"),
) -> dict[str, object]:
    """Get Value-at-Risk calculations."""
    service = get_service(request)
    return single_response(
        service.list("var"),
        confidence=confidence,
        horizon=horizon,
    )


@router.get("/greeks")
async def get_greeks(
    request: Request,
    instrument: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get portfolio greeks."""
    service = get_service(request)
    records = service.list("greeks", filters={"instrument": instrument})
    return paginated_response(records, page, page_size)


@router.get("/stress")
async def get_stress_tests(
    request: Request,
) -> dict[str, object]:
    """Get stress test results."""
    service = get_service(request)
    return single_response(service.list("stress_tests"))


@router.post("/circuit-breaker")
async def toggle_circuit_breaker(
    request: Request,
) -> dict[str, object]:
    """Trip or reset a circuit breaker for a strategy."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    strategy_id = str(body.get("strategy_id", ""))  # noqa: qg-empty-fallback
    action = str(body.get("action", "trip"))  # "trip" or "reset"

    strategy = service.get("strategies", strategy_id)
    if not strategy:
        return {"error": {"code": "NOT_FOUND", "message": f"Strategy {strategy_id} not found"}}

    new_status = "tripped" if action == "trip" else "active"
    updated = service.update(
        "strategies",
        strategy_id,
        {
            "circuit_breaker_status": new_status,
        },
    )
    return single_response({"action": action, "strategy": updated, "status": "ok"})


@router.post("/kill-switch")
async def kill_switch(
    request: Request,
) -> dict[str, object]:
    """Emergency kill switch — stop all activity for a scope."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    scope = str(body.get("scope", "strategy"))  # "strategy", "venue", "global"
    target_id = str(body.get("target_id", ""))  # noqa: qg-empty-fallback

    if scope == "global":
        strategies = service.list("strategies")
        for s in strategies:
            sid = str(s.get("id", ""))  # noqa: qg-empty-fallback
            _ = service.update("strategies", sid, {"kill_switch_active": True, "status": "halted"})
        return single_response(
            {"scope": "global", "strategies_halted": len(strategies), "status": "ok"}
        )
    elif scope == "strategy":
        updated = service.update(
            "strategies", target_id, {"kill_switch_active": True, "status": "halted"}
        )
        if updated:
            return single_response(
                {"scope": scope, "target_id": target_id, "strategy": updated, "status": "ok"}
            )
        return {"error": {"code": "NOT_FOUND", "message": f"Strategy {target_id} not found"}}
    elif scope == "venue":
        strategies = service.list("strategies", filters={"venue": target_id})
        for s in strategies:
            sid = str(s.get("id", ""))  # noqa: qg-empty-fallback
            _ = service.update("strategies", sid, {"kill_switch_active": True, "status": "halted"})
        return single_response(
            {
                "scope": scope,
                "target_id": target_id,
                "strategies_halted": len(strategies),
                "status": "ok",
            }
        )
    return {"error": {"code": "INVALID_SCOPE", "message": f"Unknown scope: {scope}"}}


@router.get("/exposure-types")
async def get_exposure_types(
    request: Request,
    category: str = Query(None, description="Filter by category: cefi, defi, tradfi, sports"),
) -> dict[str, object]:
    """Get available exposure type definitions for the risk dashboard.

    Returns exposure categories (gross, net, delta, vega, etc.) with their
    descriptions and aggregation rules so the frontend can render dynamic
    exposure breakdown widgets.
    """
    service = get_service(request)
    records = service.list("exposure_types", filters={"category": category})
    if records:
        return single_response(records)
    # Sensible defaults when no seeded data exists
    return single_response(
        [
            {
                "id": "gross",
                "name": "Gross Exposure",
                "description": "Sum of absolute position values",
                "aggregation": "sum_abs",
            },
            {
                "id": "net",
                "name": "Net Exposure",
                "description": "Long exposure minus short exposure",
                "aggregation": "sum_signed",
            },
            {
                "id": "delta",
                "name": "Delta Exposure",
                "description": "Portfolio delta in base currency",
                "aggregation": "sum_signed",
            },
            {
                "id": "vega",
                "name": "Vega Exposure",
                "description": "Portfolio vega — sensitivity to implied vol",
                "aggregation": "sum_signed",
            },
            {
                "id": "gamma",
                "name": "Gamma Exposure",
                "description": "Portfolio gamma — convexity of delta",
                "aggregation": "sum_signed",
            },
            {
                "id": "concentration",
                "name": "Concentration",
                "description": "Largest single-name as pct of gross",
                "aggregation": "max_pct",
            },
        ]
    )


@router.get("/defi-health")
async def get_defi_health(
    request: Request,
    chain: str = Query(None, description="Filter by chain (e.g. ethereum, arbitrum)"),
    protocol: str = Query(None, description="Filter by protocol (e.g. aave_v3)"),
    category: str = Query(None, description="Filter by category: cefi, defi, tradfi, sports"),
) -> dict[str, object]:
    """Get DeFi health metrics — health factors, LTV ratios, liquidation distances.

    Aggregates across all DeFi positions: per-protocol health factor,
    collateral vs. debt, liquidation thresholds, and real-time health status.
    """
    service = get_service(request)
    records = service.list(
        "defi_health", filters={"chain": chain, "protocol": protocol, "category": category}
    )
    if records:
        return single_response(records)
    # Sensible defaults when no seeded data exists
    return single_response(
        [
            {
                "protocol": "aave_v3",
                "chain": "ethereum",
                "health_factor": 1.85,
                "ltv_current": 0.54,
                "ltv_max": 0.825,
                "liquidation_threshold": 0.86,
                "total_collateral_usd": 2_450_000.0,
                "total_debt_usd": 1_323_000.0,
                "distance_to_liquidation_pct": 37.0,
                "status": "healthy",
            },
            {
                "protocol": "aave_v3",
                "chain": "arbitrum",
                "health_factor": 2.12,
                "ltv_current": 0.47,
                "ltv_max": 0.825,
                "liquidation_threshold": 0.86,
                "total_collateral_usd": 890_000.0,
                "total_debt_usd": 418_300.0,
                "distance_to_liquidation_pct": 45.3,
                "status": "healthy",
            },
            {
                "protocol": "compound_v3",
                "chain": "ethereum",
                "health_factor": 1.42,
                "ltv_current": 0.70,
                "ltv_max": 0.83,
                "liquidation_threshold": 0.85,
                "total_collateral_usd": 1_100_000.0,
                "total_debt_usd": 770_000.0,
                "distance_to_liquidation_pct": 17.6,
                "status": "warning",
            },
        ]
    )


@router.get("/var-summary")
async def get_var_summary(
    request: Request,
) -> dict[str, object]:
    """Get pre-computed VaR per strategy."""
    service = get_service(request)
    return single_response(service.list("var"))


@router.get("/stress-test")
async def get_stress_test(
    request: Request,
    scenario: str = Query(None),
    category: str = Query(None, description="Filter by category: cefi, defi, tradfi, sports"),
) -> dict[str, object]:
    """Get stress test results for a scenario."""
    service = get_service(request)
    records = service.list("stress_tests", filters={"scenario": scenario, "category": category})
    return single_response(records)


@router.get("/correlation-matrix")
async def get_correlation_matrix(
    request: Request,
) -> dict[str, object]:
    """Get correlation matrix."""
    service = get_service(request)
    records = service.list("correlation_matrix")
    return single_response(records)


@router.get("/regime")
async def get_regime(
    request: Request,
) -> dict[str, object]:
    """Get current market regime."""
    service = get_service(request)
    records = service.list("regime")
    if records:
        return single_response(records[0])
    return single_response(
        {
            "regime": "normal",
            "multiplier": 1.0,
            "signals": {"volatility": 0.15, "correlation": 0.3, "drawdown_velocity": 0.02},
        }
    )
