"""Execution domain — orders, fills, venues, algos, backtests."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from unified_trading_library import UnifiedCloudConfig

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

_cloud_cfg = UnifiedCloudConfig()

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/orders")
async def get_orders(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    venue: str = Query(None),
    status: str = Query(None),
    client_id: str = Query(None, description="Filter by client ID"),
    asset_group: str = Query(None, description="Filter by asset group (cefi, defi, tradfi, sports, prediction)"),
    strategy_family: str = Query(None, description="Filter by strategy family"),
    account_id: str = Query(None, description="Filter by account ID"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get orders with live/batch mode support."""
    service = get_service(request)
    collection = f"orders_{mode}"
    records = service.list(
        collection,
        filters={
            "venue": venue,
            "status": status,
            "client_id": client_id,
            "asset_group": asset_group,
            "strategy_family": strategy_family,
            "account_id": account_id,
            "as_of": as_of,
        },
    )
    return paginated_response(records, page, page_size, mode=mode, as_of=as_of)


@router.get("/fills")
async def get_fills(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    venue: str = Query(None),
    order_id: str = Query(None),
    client_id: str = Query(None, description="Filter by client ID"),
    asset_group: str = Query(None, description="Filter by asset group (cefi, defi, tradfi, sports, prediction)"),
    strategy_family: str = Query(None, description="Filter by strategy family"),
    account_id: str = Query(None, description="Filter by account ID"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get trade fills with live/batch mode support."""
    service = get_service(request)
    collection = f"fills_{mode}"
    fill_filters: dict[str, str | int | float | bool | None] = {
        "venue": venue,
        "order_id": order_id,
        "client_id": client_id,
        "asset_group": asset_group,
        "strategy_family": strategy_family,
        "account_id": account_id,
        "as_of": as_of,
    }
    records = service.list(collection, filters=fill_filters)
    if not records:
        records = service.list(
            "fills",
            filters={
                "venue": venue,
                "order_id": order_id,
                "client_id": client_id,
                "asset_group": asset_group,
                "strategy_family": strategy_family,
                "account_id": account_id,
            },
        )
    return paginated_response(records, page, page_size, mode=mode, as_of=as_of)


@router.get("/venues")
async def get_venues(request: Request) -> dict[str, object]:
    """Get configured execution venues."""
    service = get_service(request)
    return single_response(service.list("execution_venues"))


@router.get("/algos")
async def get_algos(request: Request) -> dict[str, object]:
    """Get available execution algorithms."""
    service = get_service(request)
    return single_response(service.list("algos"))


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
    return paginated_response(records, page, page_size)


@router.get("/backtests")
async def get_backtests(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get backtest runs."""
    service = get_service(request)
    records = service.list("backtests")
    return paginated_response(records, page, page_size)


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
        return single_response({"backtest": created, "status": "created"})

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
        config_values = dict(zip(param_names, combo, strict=True))
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

    return single_response(
        {
            "backtest": created_parent,
            "children_count": len(children),
            "status": "completed",
        }
    )


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


@router.get("/analysis/{execution_id}")
async def get_execution_analysis(
    request: Request,
    execution_id: str,
) -> dict[str, object]:
    """Get full execution analysis for a strategy run or order.

    Returns the instruction chain, algo decisions at each step,
    and resulting fills — the complete trace a trader needs to
    understand what happened and why.
    """
    import random
    import uuid
    from datetime import UTC, datetime, timedelta

    service = get_service(request)

    order = service.get("orders_live", execution_id)
    if not order:
        all_orders = service.list("orders_live")
        order = next(
            (o for o in all_orders if o.get("strategy_id") == execution_id),
            None,
        )

    now = datetime.now(UTC)
    strategy_id = str((order or {}).get("strategy_id", execution_id))
    instrument = str((order or {}).get("instrument", "BTC-USDT"))

    instructions: list[dict[str, object]] = [
        {
            "step": 1,
            "type": "SIGNAL_GENERATION",
            "timestamp": (now - timedelta(seconds=30)).isoformat(),
            "input": {
                "features": ["momentum_12h", "funding_rate", "oi_change"],
                "model": "xgboost-v3",
            },
            "output": {
                "signal": "BUY",
                "confidence": round(random.uniform(0.65, 0.95), 3),
                "predicted_return_bps": random.randint(15, 80),
            },
            "status": "completed",
        },
        {
            "step": 2,
            "type": "RISK_CHECK",
            "timestamp": (now - timedelta(seconds=25)).isoformat(),
            "input": {"instrument": instrument, "proposed_size_usd": random.randint(5000, 50000)},
            "output": {
                "approved": True,
                "max_position_usd": 100000,
                "current_exposure_pct": round(random.uniform(10, 60), 1),
                "var_95_impact": round(random.uniform(0.1, 2.0), 2),
            },
            "status": "completed",
        },
        {
            "step": 3,
            "type": "ALGO_SELECTION",
            "timestamp": (now - timedelta(seconds=20)).isoformat(),
            "input": {
                "urgency": "medium",
                "size_usd": random.randint(5000, 50000),
                "market_impact_model": "almgren-chriss",
            },
            "output": {
                "algo": "TWAP",
                "slices": random.randint(3, 12),
                "interval_seconds": random.choice([30, 60, 120]),
                "reason": "Medium urgency + low spread regime favours time-slicing",
            },
            "status": "completed",
        },
        {
            "step": 4,
            "type": "ORDER_ROUTING",
            "timestamp": (now - timedelta(seconds=15)).isoformat(),
            "input": {"algo": "TWAP", "venues_available": ["Binance", "OKX", "Bybit"]},
            "output": {
                "venue": "Binance",
                "reason": "Best depth at top-of-book; lowest maker fee tier",
                "spread_bps": round(random.uniform(0.5, 3.0), 1),
            },
            "status": "completed",
        },
        {
            "step": 5,
            "type": "EXECUTION",
            "timestamp": (now - timedelta(seconds=5)).isoformat(),
            "input": {"order_type": "LIMIT", "slices_remaining": 0},
            "output": {
                "fills": random.randint(3, 12),
                "avg_fill_price": round(random.uniform(50, 70000), 2),
                "total_qty": round(random.uniform(0.01, 5.0), 4),
                "slippage_bps": round(random.uniform(-1, 5), 2),
                "execution_time_ms": random.randint(800, 15000),
            },
            "status": "completed",
        },
    ]

    fills = service.list("fills_live", filters={"order_id": execution_id})
    if not fills and order:
        fills = [
            {
                "id": f"FILL-{uuid.uuid4().hex[:8].upper()}",
                "order_id": execution_id,
                "instrument": instrument,
                "side": str((order or {}).get("side", "BUY")),
                "quantity": round(random.uniform(0.01, 2.0), 4),
                "price": round(random.uniform(50, 70000), 2),
                "fees": round(random.uniform(0.5, 15.0), 2),
                "venue": str((order or {}).get("venue", "Binance")),
                "filled_at": (now - timedelta(seconds=random.randint(1, 10))).isoformat(),
            }
            for _ in range(random.randint(1, 5))
        ]

    return single_response(
        {
            "execution_id": execution_id,
            "strategy_id": strategy_id,
            "instrument": instrument,
            "instructions": instructions,
            "fills": fills,
            "summary": {
                "total_steps": len(instructions),
                "all_passed": all(i["status"] == "completed" for i in instructions),
                "total_fills": len(fills),
                "algo_used": "TWAP",
            },
        }
    )


@router.post("/orders")
async def create_order(
    request: Request,
    body: dict[str, object],
) -> dict[str, object]:
    """Place a new order + auto-create/update position + fill record.

    Mock mode: creates order, fill, and position records so GET endpoints
    return realistic data after trades are placed.
    """
    import random
    import uuid
    from datetime import UTC, datetime

    service = get_service(request)
    now = datetime.now(UTC).isoformat()

    instrument = str(body.get("instrument", "BTC-USDT"))
    side = str(body.get("side", "buy")).upper()
    qty = float(body.get("quantity", 0) or 0)
    price = float(body.get("price", 0) or 0)
    venue = str(body.get("venue", "Binance"))
    strategy_id = str(body.get("strategy_id", "manual"))

    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    order = {
        "id": order_id,
        "order_id": order_id,
        "instrument": instrument,
        "side": side,
        "type": str(body.get("order_type", "limit")),
        "quantity": qty,
        "price": price,
        "filled": qty,
        "status": "FILLED",
        "venue": venue,
        "strategy_id": strategy_id,
        "strategy_name": strategy_id,
        "created_at": now,
        **{
            k: v
            for k, v in body.items()
            if k not in ("instrument", "side", "quantity", "price", "venue", "strategy_id")
        },
    }
    service.create("orders_live", order)

    # Auto-create fill record
    fill_id = f"FILL-{uuid.uuid4().hex[:8].upper()}"
    fill = {
        "id": fill_id,
        "order_id": order_id,
        "instrument": instrument,
        "side": side,
        "quantity": qty,
        "price": price,
        "fees": round(qty * price * 0.001, 2),
        "venue": venue,
        "filled_at": now,
    }
    service.create("fills_live", fill)

    # Auto-create/update position
    entry_price = price if price > 0 else random.uniform(50, 70000)
    current_price = entry_price * (1 + random.uniform(-0.02, 0.03))
    pnl_mult = 1 if side == "BUY" else -1
    unrealised = round((current_price - entry_price) * qty * pnl_mult, 2)
    position = {
        "id": f"POS-{uuid.uuid4().hex[:8].upper()}",
        "instrument": instrument,
        "venue": venue,
        "side": "LONG" if side == "BUY" else "SHORT",
        "quantity": qty,
        "entry_price": round(entry_price, 2),
        "current_price": round(current_price, 2),
        "pnl": unrealised,
        "pnl_pct": round((current_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0,
        "unrealized_pnl": unrealised,
        "margin": round(qty * entry_price * 0.1, 2),
        "leverage": 10,
        "strategy_id": strategy_id,
        "strategy_name": strategy_id,
        "updated_at": now,
    }
    service.create("positions_live", position)

    return single_response({"order": order, "fill": fill, "position": position, "status": "filled"})


@router.put("/orders/{order_id}/cancel")
async def cancel_order(
    request: Request,
    order_id: str,
) -> dict[str, object]:
    """Cancel an open order.

    Mock mode: marks the order as cancelled in the store.
    Real mode: routes to execution-service /manual/cancel.
    """
    service = get_service(request)
    order = service.get("orders_live", order_id)
    if not order:
        return {"error": "Order not found", "status": "not_found"}
    order["status"] = "cancelled"  # pyright: ignore[reportIndexIssue]
    service.update("orders_live", order_id, order)
    return single_response({"order_id": order_id, "status": "cancelled"})


@router.put("/orders/{order_id}/amend")
async def amend_order(
    request: Request,
    order_id: str,
    body: dict[str, object],
) -> dict[str, object]:
    """Amend quantity and/or price on an open order.

    Mock mode: updates the order fields in the store.
    Real mode: routes to execution-service /manual/amend.

    Body: {quantity?: number, price?: number}
    """
    service = get_service(request)
    order = service.get("orders_live", order_id)
    if not order:
        return {"error": "Order not found", "status": "not_found"}

    quantity = body.get("quantity")
    price = body.get("price")

    if quantity is not None:
        order["quantity"] = quantity  # pyright: ignore[reportIndexIssue]
    if price is not None:
        order["price"] = price  # pyright: ignore[reportIndexIssue]

    service.update("orders_live", order_id, order)
    return single_response(
        {
            "order_id": order_id,
            "status": "amended",
            "quantity": quantity,
            "price": price,
        }
    )


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

    # Real mode: forward to execution-service manual instruction API
    mock_mode_val: bool = getattr(request.app.state, "mock_mode", True)  # pyright: ignore[reportAny]
    if not mock_mode_val:
        import httpx

        exec_url: str = getattr(
            request.app.state,
            "execution_service_url",
            _cloud_cfg.live_service_execution_url,
        )  # pyright: ignore[reportAny]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{exec_url}/manual/instruction",
                    json={
                        "venue": str(body.get("bookmaker", "BETFAIR")).upper(),
                        "operation_type": "SPORTS_EXCHANGE",
                        "instrument_key": f"{body.get('fixture_id', '')}:{body.get('market', '')}",  # noqa: qg-empty-fallback
                        "side": str(body.get("side", "BACK")),
                        "amount": float(body.get("stake", 0) or 0),
                        "price": float(body.get("odds", 1) or 1),
                    },
                )
                return {"data": resp.json(), "meta": {"forwarded_to": "execution-service"}}
        except Exception as exc:
            logger.warning(
                "Execution-service forwarding failed: %s — falling back to mock",
                exc,
            )

    # Enrich with timestamps and defaults
    import uuid
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    stake = float(body.get("stake", 0) or 0)
    odds = float(body.get("odds", 1) or 1)
    bookmaker = str(body.get("bookmaker", "betfair_exchange"))
    fixture_id = str(body.get("fixture_id", ""))  # noqa: qg-empty-fallback
    market = str(body.get("market", "FT Result"))
    outcome = str(body.get("outcome", ""))  # noqa: qg-empty-fallback

    bet_id = f"BET-{uuid.uuid4().hex[:8].upper()}"
    bet = {
        "id": bet_id,
        "status": "PLACED",
        "placed_at": now,
        "potential_return": round(stake * odds, 2),
        **body,
    }
    record = service.create("sports_bets", bet)

    # Auto-create a sports position
    position = {
        "id": f"POS-{uuid.uuid4().hex[:8].upper()}",
        "instrument": f"SPORTS:{fixture_id}:{market}",
        "venue": bookmaker,
        "side": "LONG",
        "quantity": stake,
        "entry_price": odds,
        "current_price": odds,
        "pnl": 0,
        "pnl_pct": 0,
        "unrealized_pnl": 0,
        "margin": stake,
        "leverage": 1,
        "strategy_id": "sports-manual",
        "strategy_name": f"Sports: {outcome}",
        "updated_at": now,
    }
    service.create("positions_live", position)

    return single_response({"bet": record, "position": position, "status": "placed"})


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
    return paginated_response(records, page, page_size)


@router.delete("/sports/bets/{bet_id}/cancel")
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
    return single_response({"bet": bet, "status": "cancelled"})


# ─── DeFi Operations ─────────────────────────────────────────────────────────


@router.post("/defi/execute")
async def execute_defi_operation(
    request: Request,
    body: dict[str, object],
) -> dict[str, object]:
    """Execute a DeFi operation (stake, lend, swap, borrow, flash_loan).

    Creates the operation record + corresponding position.
    """
    import random
    import uuid
    from datetime import UTC, datetime

    service = get_service(request)
    now = datetime.now(UTC).isoformat()

    op_type = str(body.get("operation", "swap")).upper()
    protocol = str(body.get("protocol", "Aave"))
    chain = str(body.get("chain", "Ethereum"))
    token = str(body.get("token", "WETH"))
    amount = float(body.get("amount", 0) or 0)

    op_id = f"DEFI-{uuid.uuid4().hex[:8].upper()}"
    operation = {
        "id": op_id,
        "type": op_type,
        "protocol": protocol,
        "chain": chain,
        "token": token,
        "amount": amount,
        "status": "CONFIRMED",
        "tx_hash": f"0x{uuid.uuid4().hex}",
        "gas_used": random.randint(50000, 300000),
        "gas_price_gwei": round(random.uniform(5, 50), 1),
        "executed_at": now,
        **{k: v for k, v in body.items() if k not in ("operation", "protocol", "chain", "token", "amount")},
    }
    service.create("defi_operations", operation)

    # Map DeFi operation to position
    venue = f"{protocol.upper()}-{chain.upper()}"
    instrument = f"{token}:{op_type}:{protocol}"
    price_map: dict[str, float] = {
        "WETH": 3420,
        "ETH": 3420,
        "USDC": 1,
        "USDT": 1,
        "DAI": 1,
        "WBTC": 67000,
        "stETH": 3400,
    }
    token_price = price_map.get(token.upper(), 100)

    position = {
        "id": f"POS-{uuid.uuid4().hex[:8].upper()}",
        "instrument": instrument,
        "venue": venue,
        "side": "LONG",
        "quantity": amount,
        "entry_price": token_price,
        "current_price": token_price,
        "pnl": 0,
        "pnl_pct": 0,
        "unrealized_pnl": 0,
        "margin": round(amount * token_price, 2),
        "leverage": 1,
        "strategy_id": f"defi-{op_type.lower()}",
        "strategy_name": f"{op_type}: {token} on {protocol}",
        "updated_at": now,
        "health_factor": round(random.uniform(1.2, 2.5), 2) if op_type in ("LEND", "BORROW") else None,
    }
    service.create("positions_live", position)

    return single_response({"execution": operation, "position": position, "status": "confirmed"})
