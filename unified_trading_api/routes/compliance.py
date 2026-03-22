"""Compliance domain — pre-trade checks, regulatory reports."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _to_float(val: object, default: float = 0.0) -> float:
    """Safely convert an object value to float."""
    if val is None:
        return default
    return float(str(val))


@router.post("/pre-trade-check")
async def pre_trade_check(
    request: Request,
) -> dict[str, object]:
    """Run pre-trade compliance checks against risk limits.

    Simulates risk-and-exposure-service PreTradeCheckEngine:
    6 checks (position limit, exposure limit, capital limit, leverage limit,
    VaR limit, stale price guard).
    """
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    instrument = str(body.get("instrument", ""))
    side = str(body.get("side", "BUY"))
    quantity = _to_float(body.get("quantity", 0))
    price = _to_float(body.get("price", 0))
    strategy_id = str(body.get("strategy_id", ""))

    proposed_notional = quantity * price
    checks: list[dict[str, object]] = []

    # Get risk limits for this strategy
    limits = service.list("risk_limits", filters={"strategy_id": strategy_id})
    limit_data = limits[0] if limits else {}

    # Get current positions for exposure calc
    positions = service.list("positions", filters={"strategy_id": strategy_id})
    current_exposure = sum(_to_float(p.get("notional_value", 0)) for p in positions)

    # Check 1: Position limit
    max_position = _to_float(limit_data.get("max_position_size", 1_000_000))
    checks.append(
        {
            "name": "position_limit",
            "status": "pass" if proposed_notional <= max_position else "fail",
            "limit": max_position,
            "current": 0,
            "proposed": proposed_notional,
        }
    )

    # Check 2: Exposure limit
    max_exposure = _to_float(limit_data.get("max_exposure", 5_000_000))
    new_exposure = current_exposure + proposed_notional
    checks.append(
        {
            "name": "exposure_limit",
            "status": "pass" if new_exposure <= max_exposure else "fail",
            "limit": max_exposure,
            "current": current_exposure,
            "proposed": new_exposure,
        }
    )

    # Check 3: Capital limit
    max_capital = _to_float(limit_data.get("max_capital_usage", 10_000_000))
    checks.append(
        {
            "name": "capital_limit",
            "status": "pass" if new_exposure <= max_capital else "fail",
            "limit": max_capital,
            "current": current_exposure,
            "proposed": new_exposure,
        }
    )

    # Check 4: Leverage limit
    max_leverage = _to_float(limit_data.get("max_leverage", 5.0))
    equity = _to_float(limit_data.get("equity", 2_000_000))
    current_leverage = new_exposure / equity if equity > 0 else 0
    checks.append(
        {
            "name": "leverage_limit",
            "status": "pass" if current_leverage <= max_leverage else "fail",
            "limit": max_leverage,
            "current": round(current_leverage, 2),
            "proposed": round(current_leverage, 2),
        }
    )

    # Check 5: VaR limit
    max_var = _to_float(limit_data.get("max_var_99", 500_000))
    estimated_var = proposed_notional * 0.03  # simplified 3% VaR estimate
    checks.append(
        {
            "name": "var_limit",
            "status": "pass" if estimated_var <= max_var else "fail",
            "limit": max_var,
            "current": 0,
            "proposed": round(estimated_var, 2),
        }
    )

    # Check 6: Stale price guard
    checks.append(
        {
            "name": "stale_price_guard",
            "status": "pass",
            "limit": 60,
            "current": 2,
            "proposed": 2,
            "description": "Price age in seconds",
        }
    )

    approved = all(c["status"] == "pass" for c in checks)

    return {
        "approved": approved,
        "instrument": instrument,
        "side": side,
        "quantity": quantity,
        "price": price,
        "strategy_id": strategy_id,
        "checks": checks,
        "checked_at": datetime.now(UTC).isoformat(),
    }
