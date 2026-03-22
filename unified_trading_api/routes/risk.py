"""Risk domain — limits, VaR, greeks, stress tests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
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
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
) -> dict[str, object]:
    """Get risk exposure. mode=live for real-time, mode=batch for T+1."""
    service = get_service(request)
    collection = f"risk_{mode}"
    records = service.list(collection, filters={"strategy_id": strategy_id})
    return {"mode": mode, "exposure": records, "as_of": as_of}


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
    data, pagination = paginate(records, page, page_size)
    return {"mode": mode, "data": data, "pagination": pagination.model_dump()}


@router.get("/var")
async def get_var(
    request: Request,
    confidence: float = Query(0.99),
    horizon: str = Query("1d"),
) -> dict[str, object]:
    """Get Value-at-Risk calculations."""
    service = get_service(request)
    return {
        "confidence": confidence,
        "horizon": horizon,
        "var": service.list("var"),
    }


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
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/stress")
async def get_stress_tests(
    request: Request,
) -> dict[str, object]:
    """Get stress test results."""
    service = get_service(request)
    return {"stress_tests": service.list("stress_tests")}


@router.post("/circuit-breaker")
async def toggle_circuit_breaker(
    request: Request,
) -> dict[str, object]:
    """Trip or reset a circuit breaker for a strategy."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    strategy_id = str(body.get("strategy_id", ""))
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
    return {"status": "ok", "action": action, "strategy": updated}


@router.post("/kill-switch")
async def kill_switch(
    request: Request,
) -> dict[str, object]:
    """Emergency kill switch — stop all activity for a scope."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    scope = str(body.get("scope", "strategy"))  # "strategy", "venue", "global"
    target_id = str(body.get("target_id", ""))

    if scope == "global":
        strategies = service.list("strategies")
        for s in strategies:
            sid = str(s.get("id", ""))
            service.update("strategies", sid, {"kill_switch_active": True, "status": "halted"})
        return {"status": "ok", "scope": "global", "strategies_halted": len(strategies)}
    elif scope == "strategy":
        updated = service.update(
            "strategies", target_id, {"kill_switch_active": True, "status": "halted"}
        )
        if updated:
            return {"status": "ok", "scope": scope, "target_id": target_id, "strategy": updated}
        return {"error": {"code": "NOT_FOUND", "message": f"Strategy {target_id} not found"}}
    elif scope == "venue":
        strategies = service.list("strategies", filters={"venue": target_id})
        for s in strategies:
            sid = str(s.get("id", ""))
            service.update("strategies", sid, {"kill_switch_active": True, "status": "halted"})
        return {
            "status": "ok",
            "scope": scope,
            "target_id": target_id,
            "strategies_halted": len(strategies),
        }
    return {"error": {"code": "INVALID_SCOPE", "message": f"Unknown scope: {scope}"}}


@router.get("/var-summary")
async def get_var_summary(
    request: Request,
) -> dict[str, object]:
    """Get pre-computed VaR per strategy."""
    service = get_service(request)
    return {"var_summary": service.list("var")}


@router.get("/stress-test")
async def get_stress_test(
    request: Request,
    scenario: str = Query(None),
) -> dict[str, object]:
    """Get stress test results for a scenario."""
    service = get_service(request)
    records = service.list("stress_tests", filters={"scenario": scenario})
    return {"stress_test": records}


@router.get("/correlation-matrix")
async def get_correlation_matrix(
    request: Request,
) -> dict[str, object]:
    """Get correlation matrix."""
    service = get_service(request)
    records = service.list("correlation_matrix")
    return {"correlation_matrix": records}


@router.get("/regime")
async def get_regime(
    request: Request,
) -> dict[str, object]:
    """Get current market regime."""
    service = get_service(request)
    records = service.list("regime")
    if records:
        return records[0]
    return {
        "regime": "normal",
        "multiplier": 1.0,
        "signals": {"volatility": 0.15, "correlation": 0.3, "drawdown_velocity": 0.02},
    }
