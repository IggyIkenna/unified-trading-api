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


@router.get("/grid-configs")
async def get_grid_configs(
    request: Request,
    domain: str = Query(None, description="Filter by domain: strategy, execution, ml"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get saved grid config library — named config sets with their fixed + grid params.

    Each grid config is a saved "folder" that references a grid run.
    Use grid_run_id to find the child backtest results.
    """
    service = get_service(request)
    records = service.list("grid_configs", filters={"domain": domain})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


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


@router.post("/backtests")
async def create_backtest(
    request: Request,
    body: dict[str, object],
) -> dict[str, object]:
    """Create a backtest — supports both single-run and grid search.

    Grid search mode (body contains 'grid_parameters'):
      Expands parameter combinations into individual backtest configs,
      persists each to the store, and returns the parent run with children.

    Single mode (no 'grid_parameters'):
      Creates a single backtest record.
    """
    import itertools
    import random
    import uuid
    from datetime import UTC, datetime

    service = get_service(request)
    now = datetime.now(UTC).isoformat()
    grid_params = body.get("grid_parameters")

    if not grid_params or not isinstance(grid_params, dict):
        # Single backtest — just create and return
        record = {
            "id": f"bt-{uuid.uuid4().hex[:8]}",
            "status": "completed",
            "progress": 100,
            "created_at": now,
            "completed_at": now,
            **body,
            "metrics": _generate_mock_metrics(),
        }
        created = service.create("backtests", record)
        return {"data": created, "status": "created"}

    # ── Grid expansion ──────────────────────────────────────────────────────
    #
    # For each grid parameter:
    #   range: expand {min, max, step} → list of values
    #   list:  use as-is
    #   toggle [true, false]: use as-is
    #
    # Then take the cartesian product of all parameter value lists
    # to generate one backtest config per combination.

    param_names: list[str] = []
    param_value_lists: list[list[object]] = []

    for param_key, param_spec in grid_params.items():
        if isinstance(param_spec, dict) and "min" in param_spec:
            # Range parameter → expand to list of values
            p_min = float(param_spec["min"])
            p_max = float(param_spec["max"])
            p_step = float(param_spec.get("step", 1))
            values: list[object] = []
            v = p_min
            while v <= p_max + p_step * 0.001:  # float tolerance
                values.append(round(v, 6))
                v += p_step
            if len(values) > 1:
                param_names.append(param_key)
                param_value_lists.append(values)
        elif isinstance(param_spec, list) and len(param_spec) > 1:
            # Set/toggle parameter → use directly
            param_names.append(param_key)
            param_value_lists.append(list(param_spec))

    # Cartesian product — cap at 500 to prevent runaway
    max_configs = 500
    combinations = list(itertools.islice(itertools.product(*param_value_lists), max_configs))

    domain = str(body.get("domain", "strategy"))
    selected_type = str(body.get("type", "unknown"))
    config_name = str(body.get("config_name", f"{selected_type} grid"))
    subscriptions = body.get("subscriptions", {})

    # Create parent grid run (acts as the "folder" for this named config)
    parent_id = f"grid-{uuid.uuid4().hex[:8]}"
    parent_record = {
        "id": parent_id,
        "type": "grid_search",
        "config_name": config_name,
        "domain": domain,
        "archetype": selected_type,
        "status": "completed",
        "grid_size": len(combinations),
        "param_names": param_names,
        "grid_parameters": dict(grid_params),
        "subscriptions": subscriptions,
        "created_at": now,
        "completed_at": now,
        "children": [],
    }

    # Also persist the grid config spec separately for the config library
    grid_config_record = {
        "id": f"gc-{uuid.uuid4().hex[:8]}",
        "grid_run_id": parent_id,
        "config_name": config_name,
        "domain": domain,
        "archetype": selected_type,
        "fixed_params": {
            "subscriptions": subscriptions,
            "type": selected_type,
        },
        "grid_parameters": dict(grid_params),
        "grid_size": len(combinations),
        "created_at": now,
    }
    service.create("grid_configs", grid_config_record)

    # Create one backtest per combination
    children: list[dict[str, object]] = []
    for i, combo in enumerate(combinations):
        config_values = dict(zip(param_names, combo))
        variant_label = " | ".join(f"{k}={v}" for k, v in config_values.items())

        child: dict[str, object] = {
            "id": f"bt-{uuid.uuid4().hex[:8]}",
            "parent_id": parent_id,
            "parent_config_name": config_name,
            "config_index": i,
            "config_name": f"{config_name} #{i + 1}",
            "variant_label": variant_label,
            "archetype": selected_type,
            "domain": domain,
            "status": "completed",
            "progress": 100,
            "parameters": config_values,
            "created_at": now,
            "completed_at": now,
            "duration_ms": random.randint(800, 12000),
            "metrics": _generate_mock_metrics(),
        }
        created_child = service.create("backtests", child)
        children.append(created_child)

    parent_record["children"] = [c["id"] for c in children]
    parent_record["best_sharpe"] = max((c["metrics"]["sharpe"] for c in children), default=0)  # pyright: ignore[reportIndexIssue]
    parent_record["best_return"] = max((c["metrics"]["totalReturn"] for c in children), default=0)  # pyright: ignore[reportIndexIssue]
    created_parent = service.create("backtests", parent_record)

    return {
        "data": created_parent,
        "children_count": len(children),
        "status": "completed",
    }


def _generate_mock_metrics() -> dict[str, object]:
    """Generate realistic-looking backtest metrics for mock mode."""
    import random

    sharpe = round(random.gauss(1.2, 0.8), 2)
    total_return = round(random.gauss(0.15, 0.12), 4)
    max_dd = round(random.uniform(0.03, 0.25), 4)
    vol = round(random.uniform(0.08, 0.35), 4)
    hit_rate = round(random.uniform(0.42, 0.68), 4)
    avg_win = round(random.uniform(100, 2000), 2)
    avg_loss = round(random.uniform(80, 1500), 2)
    trades = random.randint(50, 2000)
    fill_rate = round(random.uniform(0.92, 0.999), 4)
    avg_slippage = round(random.uniform(0.1, 3.0), 2)
    gross_pnl = round(random.gauss(50000, 30000), 2)
    fees = round(abs(gross_pnl) * random.uniform(0.005, 0.02), 2)

    return {
        "sharpe": sharpe,
        "sortino": round(sharpe * random.uniform(1.1, 1.5), 2),
        "calmar": round(sharpe * random.uniform(0.6, 1.0), 2),
        "totalReturn": total_return,
        "annualizedReturn": round(total_return * random.uniform(1.5, 3.0), 4),
        "cagr": round(total_return * random.uniform(1.2, 2.5), 4),
        "maxDrawdown": max_dd,
        "volatility": vol,
        "var95": round(vol * 1.65 * 100000, 2),
        "cvar95": round(vol * 2.0 * 100000, 2),
        "hitRate": hit_rate,
        "profitFactor": round(avg_win * hit_rate / (avg_loss * (1 - hit_rate) + 0.01), 2),
        "avgWin": avg_win,
        "avgLoss": avg_loss,
        "winLossRatio": round(avg_win / (avg_loss + 0.01), 2),
        "turnover": round(random.uniform(0.5, 5.0), 2),
        "avgSlippage": avg_slippage,
        "totalSlippage": round(avg_slippage * trades, 2),
        "fillRate": fill_rate,
        "alpha": round(random.gauss(0.02, 0.05), 4),
        "beta": round(random.gauss(0.3, 0.4), 4),
        "informationRatio": round(random.gauss(0.5, 0.4), 2),
        "grossPnl": gross_pnl,
        "netPnl": round(gross_pnl - fees, 2),
        "tradingCosts": fees,
        "fundingCosts": round(fees * random.uniform(0.1, 0.5), 2),
        "trades": trades,
    }


@router.post("/orders")
async def create_order(
    request: Request,
    body: dict[str, object],
) -> dict[str, object]:
    """Place a new order (mock: persists to store, real: routes to execution-service)."""
    service = get_service(request)
    order = service.create("orders_live", body)
    return {"data": order, "status": "created"}


# ─── Sports Betting ──────────────────────────────────────────────────────────


@router.post("/sports/bets")
async def place_sports_bet(
    request: Request,
    body: dict[str, object],
) -> dict[str, object]:
    """Place a sports bet.

    Mock mode: creates a bet record in the store with PENDING status,
    then auto-settles via paper trading adapter simulation.
    Real mode: routes to execution-service sports_execution adapters
    which connect to the bookmaker API/exchange/browser.

    Body schema matches UAC BetOrder:
      fixture_id, market, outcome, bookmaker, odds, stake, side (BACK/LAY),
      bet_type (single/accumulator), legs (for accumulators).
    """
    service = get_service(request)
    # Enrich with timestamps and defaults
    import uuid
    from datetime import UTC, datetime

    bet = {
        "id": f"BET-{uuid.uuid4().hex[:8].upper()}",
        "status": "PLACED",
        "placed_at": datetime.now(UTC).isoformat(),
        **body,
    }
    record = service.create("sports_bets", bet)
    return {"data": record, "status": "placed"}


@router.get("/sports/bets")
async def get_sports_bets(
    request: Request,
    status: str = Query(None, description="Filter by bet status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get user's sports bets with optional status filter."""
    service = get_service(request)
    records = service.list("sports_bets", filters={"status": status})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.post("/sports/bets/{bet_id}/cancel")
async def cancel_sports_bet(
    request: Request,
    bet_id: str,
) -> dict[str, object]:
    """Cancel an unmatched sports bet."""
    service = get_service(request)
    bet = service.get("sports_bets", bet_id)
    if not bet:
        return {"error": "Bet not found", "status": "not_found"}
    bet["status"] = "CANCELLED"  # pyright: ignore[reportIndexIssue]
    service.update("sports_bets", bet_id, bet)
    return {"data": bet, "status": "cancelled"}
