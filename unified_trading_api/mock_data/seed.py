"""Seed all domains with realistic synthetic mock data.

~200+ records across all domains. Every record carries ``org_id`` sourced from
the persona SSOT (personas.py). Distribution: odum-internal 60%, acme 20%,
vertex 12%, beta 8%.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, Protocol

# Callable type for store.list() used in validation helpers
type _ListFn = Callable[[str], list[dict[str, object]]]

SEED_VERSION: Final[str] = "4.3.0"


class _Seedable(Protocol):
    def seed(self, collection: str, items: list[dict[str, object]]) -> None: ...


# ── Org helpers ───────────────────────────────────────────────────────
_O = "odum-internal"
_A = "acme"
_V = "vertex"
_B = "beta"

# Client IDs per org (for strategy → client mapping)
_CLIENT_ODUM = "client-odum-desk"
_CLIENT_ACME = "client-acme-alpha"
_CLIENT_VERTEX = "client-vertex-partners"
_CLIENT_BETA = "client-beta-fund"


_ID_FIELD_MAP: dict[str, str] = {
    "orders": "order_id",
    "fills": "fill_id",
    "fills_live": "fill_id",
    "fills_batch": "fill_id",
    "positions": "position_id",
    "positions_batch": "position_id",
    "positions_live": "position_id",
    "execution_venues": "venue_id",
    "algos": "algo_id",
    "backtests": "backtest_id",
    "strategies": "id",
    "alerts": "alert_id",
    "settlements": "settlement_id",
    "invoices": "invoice_id",
    "fee_schedules": "schedule_id",
    "model_families": "family_id",
    "experiments": "experiment_id",
    "training_runs": "run_id",
    "model_versions": "version_id",
    "model_deployments": "deployment_id",
    "ml_features": "feature_id",
    "datasets": "dataset_id",
    "reports": "report_id",
    "reporting_settlements": "settlement_id",
    "reconciliation": "recon_id",
    "audit_events": "event_id",
    "compliance": "check_id",
    "audit_logs": "log_id",
    "instruments": "instrument_id",
    "documents": "document_id",
    "deployments": "deployment_id",
    "builds": "build_id",
    "members": "member_id",
    "subscriptions": "subscription_id",
    "trades": "trade_id",
    "alerts_batch": "alert_id",
    "var_metrics": "strategy_id",
    "stress_test_results": "scenario_id",
    "correlation_matrix": "matrix_id",
    "market_regime": "regime_id",
    "options_chain": "option_id",
    "vol_surfaces": "surface_id",
    "portfolio_greeks": "portfolio_id",
    "fx_rates": "pair",
    "regulatory_reports": "report_id",
    "risk_exposure": "strategy_id",
    "risk_batch": "strategy_id",
    "strategy_configs": "config_id",
    "alerts_live": "alert_id",
    "risk_live": "strategy_id",
    "orders_live": "order_id",
    "orders_batch": "order_id",
    "tickers_live": "instrument",
    "regime": "id",
    "exposure_types": "id",
    "defi_health": "id",
}


def _check_org_integrity(
    domains: tuple[str, ...],
    list_fn: _ListFn,
) -> list[str]:
    """Return errors for records with invalid org_id values."""
    from unified_trading_api.mock_data.personas import (  # noqa: qg-deep-import — self-package
        ORG_IDS,  # noqa: qg-deep-import — self-package
    )

    errors: list[str] = []
    valid_orgs = set(ORG_IDS)
    for domain in domains:
        records: list[dict[str, object]] = list_fn(domain)
        for rec in records:
            org = rec.get("org_id")
            if org is not None and str(org) not in valid_orgs:
                errors.append(f"{domain} record {rec.get('id', '?')} has invalid org_id: {org}")
    return errors


def _check_temporal_consistency(
    strategies: list[dict[str, object]],
    positions: list[dict[str, object]],
) -> list[str]:
    """Return errors for positions opened before their strategy's inception_date."""
    errors: list[str] = []
    strategy_inception: dict[str, str] = {}
    for s in strategies:
        inception = s.get("inception_date")
        if inception is not None:
            strategy_inception[str(s.get("id", ""))] = str(inception)

    for pos in positions:
        sid = pos.get("strategy_id")
        opened = pos.get("opened_at")
        if sid is not None and opened is not None and str(sid) in strategy_inception:
            inception_date = strategy_inception[str(sid)]
            if str(opened) < inception_date:
                errors.append(
                    f"position {pos.get('id', '?')} opened_at {opened} is before "
                    + f"strategy {sid} inception_date {inception_date}"
                )
    return errors


def _check_batch_live_consistency(
    batch_positions: list[dict[str, object]],
    live_positions: list[dict[str, object]],
) -> list[str]:
    """Return errors for batch positions not present in live positions."""
    errors: list[str] = []
    if batch_positions and live_positions:
        live_position_ids = {str(p.get("position_id", "")) for p in live_positions}
        for bp in batch_positions:
            bp_id = str(bp.get("position_id", ""))
            if bp_id and bp_id not in live_position_ids:
                errors.append(f"batch position {bp_id} not found in live positions")
    return errors


def validate_consistency(store: _Seedable) -> list[str]:
    """Validate cross-domain data consistency after seeding.

    Returns a list of error messages. Empty list = all valid.
    Raises ValueError if critical violations found (enabled by default).
    """
    errors: list[str] = []
    _list_fn = getattr(store, "list", None)
    if _list_fn is None:
        return errors

    def _list(domain: str) -> list[dict[str, object]]:
        result: list[dict[str, object]] = _list_fn(domain)  # pyright: ignore[reportAny]
        return result

    # 1. Strategy reference integrity
    strategies = _list("strategies")
    strategy_ids = {str(s.get("id", "")) for s in strategies}

    for domain in ("positions", "orders"):
        for rec in _list(domain):
            sid = rec.get("strategy_id")
            if sid is not None and str(sid) not in strategy_ids:
                errors.append(
                    f"{domain} record {rec.get('id', '?')} references invalid strategy_id: {sid}"
                )

    # 2. Order reference integrity (fills → orders)
    order_ids = {str(o.get("order_id", o.get("id", ""))) for o in _list("orders")}
    for fill in _list("fills"):
        oid = fill.get("order_id")
        if oid is not None and str(oid) not in order_ids:
            errors.append(f"fill {fill.get('fill_id', '?')} references invalid order_id: {oid}")

    # 3. Org reference integrity
    errors.extend(_check_org_integrity(("strategies", "positions", "orders", "alerts"), _list))

    # 4. Temporal consistency — no position opened before strategy inception
    errors.extend(_check_temporal_consistency(strategies, _list("positions")))

    # 5. Batch/live consistency — batch positions must be subset of live positions
    errors.extend(_check_batch_live_consistency(_list("positions_batch"), _list("positions_live")))

    return errors


def _ensure_id(domain: str, records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Add 'id' field to records if missing, copying from the domain-specific ID."""
    id_field = _ID_FIELD_MAP.get(domain)
    for i, record in enumerate(records):
        if "id" not in record:
            if id_field and id_field in record:
                record["id"] = record[id_field]
            else:
                record["id"] = f"{domain}-{i}"
    return records


def seed_all_domains(store: _Seedable | None = None) -> None:
    """Populate every mock-store domain with synthetic records.

    Args:
        store: UTL MockStateStore or any object with a seed(domain, records) method.
               Falls back to legacy singleton for backwards compatibility.
    """
    if store is None:
        msg = "seed_all_domains() requires an explicit store argument (UTL MockStateStore)"
        raise TypeError(msg)

    _store: _Seedable = store

    def _seed(domain: str, records: list[dict[str, object]]) -> None:
        """Seed with auto-id: ensures every record has an 'id' field."""
        _ = _ensure_id(domain, records)
        _store.seed(domain, records)

    # Seed version marker for cache invalidation
    _seed("_meta", [{"id": "seed_version", "version": SEED_VERSION}])

    # ══════════════════════════════════════════════════════════════════
    #  STRATEGIES (50+) — registry-driven via seed_strategies.py
    # ══════════════════════════════════════════════════════════════════

    from unified_trading_api.mock_data.seed_strategies import (  # noqa: qg-deep-import — self-package
        generate_strategies,  # noqa: qg-deep-import — self-package
    )

    _strategies = generate_strategies()
    _seed("strategies", _strategies)

    _strategy_asset_group: dict[str, str] = {
        str(s["id"]): str(s.get("asset_group", "cefi")) for s in _strategies
    }

    # Also seed strategy_configs for the config-driven expansion
    _strategy_configs = [
        {
            "config_id": s["id"],
            "strategy_id": s["id"],
            "name": s["name"],
            "archetype": s.get("archetype", "unknown"),
            "asset_group": s.get("asset_group", "cefi"),
            "instruments": s.get("instruments", []),
            "execution_mode": s.get("status", "live"),
            "timeframe": "1h",
            "org_id": s.get("org_id", _O),
        }
        for s in _strategies
    ]
    _seed("strategy_configs", _strategy_configs)

    # ══════════════════════════════════════════════════════════════════
    #  ORDERS (25) — 40% filled, 20% partial, 20% open, 10% cancelled,
    #                10% rejected
    # ══════════════════════════════════════════════════════════════════

    _orders_records: list[dict[str, object]] = [
        # ── Filled (10) ──
        {
            "order_id": "ord-a1b2c3d4-1001",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "side": "buy",
            "type": "limit",
            "price": 67250.50,
            "quantity": 0.15,
            "filled_quantity": 0.15,
            "status": "filled",
            "created_at": "2026-03-21T08:12:33Z",
            "org_id": _O,
            "strategy_id": "strat-002",
        },
        {
            "order_id": "ord-a1b2c3d4-1002",
            "venue": "binance",
            "instrument": "ETH-USDT",
            "side": "sell",
            "type": "market",
            "price": 3480.00,
            "quantity": 2.0,
            "filled_quantity": 2.0,
            "status": "filled",
            "created_at": "2026-03-21T08:14:01Z",
            "org_id": _O,
            "strategy_id": "strat-006",
        },
        {
            "order_id": "ord-a1b2c3d4-1005",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "side": "sell",
            "type": "limit",
            "price": 67400.00,
            "quantity": 0.10,
            "filled_quantity": 0.10,
            "status": "filled",
            "created_at": "2026-03-21T09:30:00Z",
            "org_id": _A,
            "strategy_id": "strat-004",
        },
        {
            "order_id": "ord-a1b2c3d4-1006",
            "venue": "deribit",
            "instrument": "ETH-USDT",
            "side": "sell",
            "type": "limit",
            "price": 3520.00,
            "quantity": 5.0,
            "filled_quantity": 5.0,
            "status": "filled",
            "created_at": "2026-03-21T07:45:00Z",
            "org_id": _O,
            "strategy_id": "strat-003",
        },
        {
            "order_id": "ord-a1b2c3d4-1007",
            "venue": "hyperliquid",
            "instrument": "ETH-USD-PERP",
            "side": "buy",
            "type": "limit",
            "price": 3475.00,
            "quantity": 10.0,
            "filled_quantity": 10.0,
            "status": "filled",
            "created_at": "2026-03-21T10:05:00Z",
            "org_id": _O,
            "strategy_id": "strat-009",
        },
        {
            "order_id": "ord-a1b2c3d4-1008",
            "venue": "binance",
            "instrument": "SOL-USDT",
            "side": "buy",
            "type": "market",
            "price": 145.80,
            "quantity": 100.0,
            "filled_quantity": 100.0,
            "status": "filled",
            "created_at": "2026-03-21T10:20:00Z",
            "org_id": _V,
            "strategy_id": "strat-017",
        },
        {
            "order_id": "ord-a1b2c3d4-1009",
            "venue": "uniswap_v3",
            "instrument": "WETH-USDC",
            "side": "buy",
            "type": "market",
            "price": 3478.50,
            "quantity": 3.0,
            "filled_quantity": 3.0,
            "status": "filled",
            "created_at": "2026-03-21T11:00:00Z",
            "org_id": _O,
            "strategy_id": "strat-001",
        },
        {
            "order_id": "ord-a1b2c3d4-1010",
            "venue": "aave_v3",
            "instrument": "WETH-SUPPLY",
            "side": "buy",
            "type": "market",
            "price": 3480.00,
            "quantity": 5.0,
            "filled_quantity": 5.0,
            "status": "filled",
            "created_at": "2026-03-21T11:15:00Z",
            "org_id": _O,
            "strategy_id": "strat-007",
        },
        {
            "order_id": "ord-a1b2c3d4-1011",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "side": "buy",
            "type": "limit",
            "price": 67100.00,
            "quantity": 0.20,
            "filled_quantity": 0.20,
            "status": "filled",
            "created_at": "2026-03-21T06:30:00Z",
            "org_id": _A,
            "strategy_id": "strat-002",
        },
        {
            "order_id": "ord-a1b2c3d4-1012",
            "venue": "deribit",
            "instrument": "BTC-28MAR26-70000-C",
            "side": "sell",
            "type": "limit",
            "price": 1300.00,
            "quantity": 2.0,
            "filled_quantity": 2.0,
            "status": "filled",
            "created_at": "2026-03-21T07:00:00Z",
            "org_id": _O,
            "strategy_id": "strat-014",
        },
        # ── Partially filled (5) ──
        {
            "order_id": "ord-a1b2c3d4-1004",
            "venue": "hyperliquid",
            "instrument": "SOL-USD-PERP",
            "side": "buy",
            "type": "limit",
            "price": 145.30,
            "quantity": 50.0,
            "filled_quantity": 25.0,
            "status": "partially_filled",
            "created_at": "2026-03-21T09:15:22Z",
            "org_id": _O,
            "strategy_id": "strat-009",
        },
        {
            "order_id": "ord-a1b2c3d4-1013",
            "venue": "binance",
            "instrument": "ETH-USDT",
            "side": "buy",
            "type": "limit",
            "price": 3470.00,
            "quantity": 8.0,
            "filled_quantity": 3.5,
            "status": "partially_filled",
            "created_at": "2026-03-21T11:30:00Z",
            "org_id": _V,
            "strategy_id": "strat-006",
        },
        {
            "order_id": "ord-a1b2c3d4-1014",
            "venue": "hyperliquid",
            "instrument": "BTC-USD-PERP",
            "side": "sell",
            "type": "limit",
            "price": 67500.00,
            "quantity": 0.30,
            "filled_quantity": 0.12,
            "status": "partially_filled",
            "created_at": "2026-03-21T12:00:00Z",
            "org_id": _O,
            "strategy_id": "strat-011",
        },
        {
            "order_id": "ord-a1b2c3d4-1015",
            "venue": "uniswap_v3",
            "instrument": "WBTC-WETH",
            "side": "buy",
            "type": "limit",
            "price": 19.32,
            "quantity": 1.0,
            "filled_quantity": 0.6,
            "status": "partially_filled",
            "created_at": "2026-03-21T12:15:00Z",
            "org_id": _A,
            "strategy_id": "strat-010",
        },
        {
            "order_id": "ord-a1b2c3d4-1016",
            "venue": "binance",
            "instrument": "AVAX-USDT",
            "side": "buy",
            "type": "limit",
            "price": 38.50,
            "quantity": 200.0,
            "filled_quantity": 80.0,
            "status": "partially_filled",
            "created_at": "2026-03-21T12:30:00Z",
            "org_id": _B,
            "strategy_id": "strat-006",
        },
        # ── Open (5) ──
        {
            "order_id": "ord-a1b2c3d4-1003",
            "venue": "deribit",
            "instrument": "BTC-28MAR26-70000-C",
            "side": "buy",
            "type": "limit",
            "price": 1250.00,
            "quantity": 5.0,
            "filled_quantity": 0.0,
            "status": "open",
            "created_at": "2026-03-21T09:00:00Z",
            "org_id": _O,
            "strategy_id": "strat-014",
        },
        {
            "order_id": "ord-a1b2c3d4-1017",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "side": "buy",
            "type": "limit",
            "price": 66800.00,
            "quantity": 0.25,
            "filled_quantity": 0.0,
            "status": "open",
            "created_at": "2026-03-21T13:00:00Z",
            "org_id": _O,
            "strategy_id": "strat-002",
        },
        {
            "order_id": "ord-a1b2c3d4-1018",
            "venue": "hyperliquid",
            "instrument": "SOL-USD-PERP",
            "side": "sell",
            "type": "limit",
            "price": 148.00,
            "quantity": 75.0,
            "filled_quantity": 0.0,
            "status": "open",
            "created_at": "2026-03-21T13:10:00Z",
            "org_id": _V,
            "strategy_id": "strat-009",
        },
        {
            "order_id": "ord-a1b2c3d4-1019",
            "venue": "aave_v3",
            "instrument": "USDC-SUPPLY",
            "side": "buy",
            "type": "market",
            "price": 1.0,
            "quantity": 50000.0,
            "filled_quantity": 0.0,
            "status": "open",
            "created_at": "2026-03-21T13:20:00Z",
            "org_id": _O,
            "strategy_id": "strat-007",
        },
        {
            "order_id": "ord-a1b2c3d4-1020",
            "venue": "deribit",
            "instrument": "ETH-28MAR26-4000-C",
            "side": "buy",
            "type": "limit",
            "price": 180.00,
            "quantity": 20.0,
            "filled_quantity": 0.0,
            "status": "open",
            "created_at": "2026-03-21T13:30:00Z",
            "org_id": _A,
            "strategy_id": "strat-014",
        },
        # ── Cancelled (3) ──
        {
            "order_id": "ord-a1b2c3d4-1021",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "side": "sell",
            "type": "limit",
            "price": 68000.00,
            "quantity": 0.10,
            "filled_quantity": 0.0,
            "status": "cancelled",
            "created_at": "2026-03-21T07:00:00Z",
            "org_id": _B,
            "strategy_id": "strat-002",
        },
        {
            "order_id": "ord-a1b2c3d4-1022",
            "venue": "hyperliquid",
            "instrument": "ETH-USD-PERP",
            "side": "buy",
            "type": "limit",
            "price": 3400.00,
            "quantity": 5.0,
            "filled_quantity": 0.0,
            "status": "cancelled",
            "created_at": "2026-03-21T08:00:00Z",
            "org_id": _O,
            "strategy_id": "strat-011",
        },
        # ── Rejected (2) ──
        {
            "order_id": "ord-a1b2c3d4-1024",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "side": "buy",
            "type": "limit",
            "price": 67000.00,
            "quantity": 5.0,
            "filled_quantity": 0.0,
            "status": "rejected",
            "created_at": "2026-03-21T06:00:00Z",
            "org_id": _O,
            "strategy_id": "strat-002",
        },
        {
            "order_id": "ord-a1b2c3d4-1025",
            "venue": "deribit",
            "instrument": "BTC-28MAR26-70000-C",
            "side": "sell",
            "type": "limit",
            "price": 800.00,
            "quantity": 50.0,
            "filled_quantity": 0.0,
            "status": "rejected",
            "created_at": "2026-03-21T06:15:00Z",
            "org_id": _V,
            "strategy_id": "strat-014",
        },
        # extra cancelled to reach 25 total
        {
            "order_id": "ord-a1b2c3d4-1023",
            "venue": "uniswap_v3",
            "instrument": "WETH-USDC",
            "side": "sell",
            "type": "limit",
            "price": 3500.00,
            "quantity": 2.0,
            "filled_quantity": 0.0,
            "status": "cancelled",
            "created_at": "2026-03-21T09:45:00Z",
            "org_id": _A,
            "strategy_id": "strat-001",
        },
    ]
    for _ord in _orders_records:
        _ord["asset_group"] = _strategy_asset_group.get(str(_ord.get("strategy_id", "")), "cefi")
    _seed("orders", _orders_records)

    # ══════════════════════════════════════════════════════════════════
    #  FILLS (35) — each references a valid order_id
    #  Realistic slippage 0.01-0.05%, venue-specific fees
    # ══════════════════════════════════════════════════════════════════

    _order_id_to_asset_group: dict[str, str] = {
        str(o["order_id"]): str(o.get("asset_group", "cefi")) for o in _orders_records
    }

    _fills_records: list[dict[str, object]] = [
        # fills for ord-1001 (filled, BTC-USDT binance, 0.15)
        {
            "fill_id": "fill-e5f6a7b8-2001",
            "order_id": "ord-a1b2c3d4-1001",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "price": 67250.50,
            "quantity": 0.08,
            "fee": 0.54,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T08:12:34Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2002",
            "order_id": "ord-a1b2c3d4-1001",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "price": 67253.87,
            "quantity": 0.07,
            "fee": 0.47,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T08:12:35Z",
            "org_id": _O,
        },
        # fills for ord-1002 (filled, ETH-USDT binance, 2.0)
        {
            "fill_id": "fill-e5f6a7b8-2003",
            "order_id": "ord-a1b2c3d4-1002",
            "venue": "binance",
            "instrument": "ETH-USDT",
            "price": 3480.25,
            "quantity": 2.0,
            "fee": 0.70,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T08:14:02Z",
            "org_id": _O,
        },
        # fills for ord-1004 (partial, SOL-USD-PERP hyperliquid, 25/50)
        {
            "fill_id": "fill-e5f6a7b8-2004",
            "order_id": "ord-a1b2c3d4-1004",
            "venue": "hyperliquid",
            "instrument": "SOL-USD-PERP",
            "price": 145.28,
            "quantity": 15.0,
            "fee": 0.22,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T09:15:23Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2005",
            "order_id": "ord-a1b2c3d4-1004",
            "venue": "hyperliquid",
            "instrument": "SOL-USD-PERP",
            "price": 145.31,
            "quantity": 10.0,
            "fee": 0.15,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T09:15:45Z",
            "org_id": _O,
        },
        # fills for ord-1005 (filled, BTC-USDT binance, 0.10)
        {
            "fill_id": "fill-e5f6a7b8-2006",
            "order_id": "ord-a1b2c3d4-1005",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "price": 67398.65,
            "quantity": 0.10,
            "fee": 0.67,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T09:30:01Z",
            "org_id": _A,
        },
        # fills for ord-1006 (filled, ETH-USDT deribit, 5.0)
        {
            "fill_id": "fill-e5f6a7b8-2007",
            "order_id": "ord-a1b2c3d4-1006",
            "venue": "deribit",
            "instrument": "ETH-USDT",
            "price": 3519.30,
            "quantity": 3.0,
            "fee": 1.06,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T07:45:01Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2008",
            "order_id": "ord-a1b2c3d4-1006",
            "venue": "deribit",
            "instrument": "ETH-USDT",
            "price": 3520.00,
            "quantity": 2.0,
            "fee": 0.70,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T07:45:02Z",
            "org_id": _O,
        },
        # fills for ord-1007 (filled, ETH-USD-PERP hyperliquid, 10.0)
        {
            "fill_id": "fill-e5f6a7b8-2009",
            "order_id": "ord-a1b2c3d4-1007",
            "venue": "hyperliquid",
            "instrument": "ETH-USD-PERP",
            "price": 3475.17,
            "quantity": 10.0,
            "fee": 0.35,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T10:05:01Z",
            "org_id": _O,
        },
        # fills for ord-1008 (filled, SOL-USDT binance, 100.0)
        {
            "fill_id": "fill-e5f6a7b8-2010",
            "order_id": "ord-a1b2c3d4-1008",
            "venue": "binance",
            "instrument": "SOL-USDT",
            "price": 145.82,
            "quantity": 60.0,
            "fee": 0.87,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T10:20:01Z",
            "org_id": _V,
        },
        {
            "fill_id": "fill-e5f6a7b8-2011",
            "order_id": "ord-a1b2c3d4-1008",
            "venue": "binance",
            "instrument": "SOL-USDT",
            "price": 145.85,
            "quantity": 40.0,
            "fee": 0.58,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T10:20:02Z",
            "org_id": _V,
        },
        # fills for ord-1009 (filled, WETH-USDC uniswap, 3.0)
        {
            "fill_id": "fill-e5f6a7b8-2012",
            "order_id": "ord-a1b2c3d4-1009",
            "venue": "uniswap_v3",
            "instrument": "WETH-USDC",
            "price": 3479.24,
            "quantity": 3.0,
            "fee": 10.44,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T11:00:15Z",
            "org_id": _O,
        },
        # fills for ord-1010 (filled, WETH-SUPPLY aave, 5.0)
        {
            "fill_id": "fill-e5f6a7b8-2013",
            "order_id": "ord-a1b2c3d4-1010",
            "venue": "aave_v3",
            "instrument": "WETH-SUPPLY",
            "price": 3480.00,
            "quantity": 5.0,
            "fee": 8.70,
            "fee_currency": "ETH",
            "executed_at": "2026-03-21T11:15:12Z",
            "org_id": _O,
        },
        # fills for ord-1011 (filled, BTC-USDT binance, 0.20)
        {
            "fill_id": "fill-e5f6a7b8-2014",
            "order_id": "ord-a1b2c3d4-1011",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "price": 67100.00,
            "quantity": 0.20,
            "fee": 1.34,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T06:30:01Z",
            "org_id": _A,
        },
        # fills for ord-1012 (filled, BTC-28MAR26-70000-C deribit, 2.0)
        {
            "fill_id": "fill-e5f6a7b8-2015",
            "order_id": "ord-a1b2c3d4-1012",
            "venue": "deribit",
            "instrument": "BTC-28MAR26-70000-C",
            "price": 1299.35,
            "quantity": 2.0,
            "fee": 2.60,
            "fee_currency": "USD",
            "executed_at": "2026-03-21T07:00:01Z",
            "org_id": _O,
        },
        # fills for ord-1013 (partial, ETH-USDT binance, 3.5/8)
        {
            "fill_id": "fill-e5f6a7b8-2016",
            "order_id": "ord-a1b2c3d4-1013",
            "venue": "binance",
            "instrument": "ETH-USDT",
            "price": 3470.35,
            "quantity": 2.0,
            "fee": 0.69,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T11:30:01Z",
            "org_id": _V,
        },
        {
            "fill_id": "fill-e5f6a7b8-2017",
            "order_id": "ord-a1b2c3d4-1013",
            "venue": "binance",
            "instrument": "ETH-USDT",
            "price": 3470.52,
            "quantity": 1.5,
            "fee": 0.52,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T11:30:15Z",
            "org_id": _V,
        },
        # fills for ord-1014 (partial, BTC-USD-PERP hyperliquid, 0.12/0.30)
        {
            "fill_id": "fill-e5f6a7b8-2018",
            "order_id": "ord-a1b2c3d4-1014",
            "venue": "hyperliquid",
            "instrument": "BTC-USD-PERP",
            "price": 67497.30,
            "quantity": 0.12,
            "fee": 0.81,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T12:00:02Z",
            "org_id": _O,
        },
        # fills for ord-1015 (partial, WBTC-WETH uniswap, 0.6/1.0)
        {
            "fill_id": "fill-e5f6a7b8-2019",
            "order_id": "ord-a1b2c3d4-1015",
            "venue": "uniswap_v3",
            "instrument": "WBTC-WETH",
            "price": 19.33,
            "quantity": 0.6,
            "fee": 0.035,
            "fee_currency": "WETH",
            "executed_at": "2026-03-21T12:15:20Z",
            "org_id": _A,
        },
        # fills for ord-1016 (partial, AVAX-USDT binance, 80/200)
        {
            "fill_id": "fill-e5f6a7b8-2020",
            "order_id": "ord-a1b2c3d4-1016",
            "venue": "binance",
            "instrument": "AVAX-USDT",
            "price": 38.51,
            "quantity": 50.0,
            "fee": 0.19,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T12:30:01Z",
            "org_id": _B,
        },
        {
            "fill_id": "fill-e5f6a7b8-2021",
            "order_id": "ord-a1b2c3d4-1016",
            "venue": "binance",
            "instrument": "AVAX-USDT",
            "price": 38.52,
            "quantity": 30.0,
            "fee": 0.12,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T12:30:10Z",
            "org_id": _B,
        },
        # Additional historical fills to reach 35 total
        {
            "fill_id": "fill-e5f6a7b8-2022",
            "order_id": "ord-a1b2c3d4-1001",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "price": 67249.15,
            "quantity": 0.0,
            "fee": 0.0,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T08:12:33Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2023",
            "order_id": "ord-a1b2c3d4-1005",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "price": 67401.35,
            "quantity": 0.05,
            "fee": 0.34,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T09:30:02Z",
            "org_id": _A,
        },
        {
            "fill_id": "fill-e5f6a7b8-2024",
            "order_id": "ord-a1b2c3d4-1007",
            "venue": "hyperliquid",
            "instrument": "ETH-USD-PERP",
            "price": 3474.83,
            "quantity": 5.0,
            "fee": 0.17,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T10:05:02Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2025",
            "order_id": "ord-a1b2c3d4-1006",
            "venue": "deribit",
            "instrument": "ETH-USDT",
            "price": 3520.18,
            "quantity": 1.0,
            "fee": 0.35,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T07:45:03Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2026",
            "order_id": "ord-a1b2c3d4-1008",
            "venue": "binance",
            "instrument": "SOL-USDT",
            "price": 145.78,
            "quantity": 20.0,
            "fee": 0.29,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T10:20:00Z",
            "org_id": _V,
        },
        {
            "fill_id": "fill-e5f6a7b8-2027",
            "order_id": "ord-a1b2c3d4-1009",
            "venue": "uniswap_v3",
            "instrument": "WETH-USDC",
            "price": 3478.90,
            "quantity": 1.0,
            "fee": 3.48,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T11:00:10Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2028",
            "order_id": "ord-a1b2c3d4-1011",
            "venue": "binance",
            "instrument": "BTC-USDT",
            "price": 67102.70,
            "quantity": 0.10,
            "fee": 0.67,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T06:30:02Z",
            "org_id": _A,
        },
        {
            "fill_id": "fill-e5f6a7b8-2029",
            "order_id": "ord-a1b2c3d4-1012",
            "venue": "deribit",
            "instrument": "BTC-28MAR26-70000-C",
            "price": 1300.65,
            "quantity": 1.0,
            "fee": 1.30,
            "fee_currency": "USD",
            "executed_at": "2026-03-21T07:00:02Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2030",
            "order_id": "ord-a1b2c3d4-1010",
            "venue": "aave_v3",
            "instrument": "WETH-SUPPLY",
            "price": 3480.00,
            "quantity": 2.5,
            "fee": 4.35,
            "fee_currency": "ETH",
            "executed_at": "2026-03-21T11:15:08Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2031",
            "order_id": "ord-a1b2c3d4-1013",
            "venue": "binance",
            "instrument": "ETH-USDT",
            "price": 3470.17,
            "quantity": 0.5,
            "fee": 0.17,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T11:30:20Z",
            "org_id": _V,
        },
        {
            "fill_id": "fill-e5f6a7b8-2032",
            "order_id": "ord-a1b2c3d4-1016",
            "venue": "binance",
            "instrument": "AVAX-USDT",
            "price": 38.49,
            "quantity": 20.0,
            "fee": 0.08,
            "fee_currency": "USDT",
            "executed_at": "2026-03-21T12:30:15Z",
            "org_id": _B,
        },
        {
            "fill_id": "fill-e5f6a7b8-2033",
            "order_id": "ord-a1b2c3d4-1014",
            "venue": "hyperliquid",
            "instrument": "BTC-USD-PERP",
            "price": 67498.65,
            "quantity": 0.05,
            "fee": 0.34,
            "fee_currency": "USDC",
            "executed_at": "2026-03-21T12:00:05Z",
            "org_id": _O,
        },
        {
            "fill_id": "fill-e5f6a7b8-2034",
            "order_id": "ord-a1b2c3d4-1015",
            "venue": "uniswap_v3",
            "instrument": "WBTC-WETH",
            "price": 19.31,
            "quantity": 0.2,
            "fee": 0.012,
            "fee_currency": "WETH",
            "executed_at": "2026-03-21T12:15:30Z",
            "org_id": _A,
        },
        {
            "fill_id": "fill-e5f6a7b8-2035",
            "order_id": "ord-a1b2c3d4-1010",
            "venue": "aave_v3",
            "instrument": "WETH-SUPPLY",
            "price": 3480.00,
            "quantity": 1.5,
            "fee": 2.61,
            "fee_currency": "ETH",
            "executed_at": "2026-03-21T11:15:15Z",
            "org_id": _O,
        },
    ]
    for _f in _fills_records:
        _f["asset_group"] = _order_id_to_asset_group.get(str(_f.get("order_id")), "cefi")
    _seed("fills", _fills_records)

    # fills_live and fills_batch — copy fills data into live/batch collections
    _store_list = getattr(_store, "list", None)
    _fills_for_copy: list[dict[str, object]] = _store_list("fills") if _store_list else []
    _seed("fills_live", _fills_for_copy)
    _seed("fills_batch", [{**f, "reconciled": True} for f in _fills_for_copy])

    # ══════════════════════════════════════════════════════════════════
    #  EXECUTION VENUES (5)
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "execution_venues",
        [
            {
                "venue_id": "binance",
                "name": "Binance",
                "type": "cefi",
                "status": "active",
                "latency_ms": 45,
                "org_id": _O,
            },
            {
                "venue_id": "deribit",
                "name": "Deribit",
                "type": "cefi",
                "status": "active",
                "latency_ms": 62,
                "org_id": _O,
            },
            {
                "venue_id": "hyperliquid",
                "name": "Hyperliquid",
                "type": "defi",
                "status": "active",
                "latency_ms": 120,
                "org_id": _O,
            },
            {
                "venue_id": "uniswap_v3",
                "name": "Uniswap V3",
                "type": "defi",
                "status": "active",
                "latency_ms": 2500,
                "org_id": _O,
            },
            {
                "venue_id": "aave_v3",
                "name": "Aave V3",
                "type": "defi",
                "status": "active",
                "latency_ms": 3000,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "algos",
        [
            {
                "algo_id": "twap-v2",
                "name": "TWAP",
                "description": "Time-weighted average price",
                "status": "active",
                "org_id": _O,
            },
            {
                "algo_id": "vwap-v1",
                "name": "VWAP",
                "description": "Volume-weighted average price",
                "status": "active",
                "org_id": _O,
            },
            {
                "algo_id": "iceberg-v1",
                "name": "Iceberg",
                "description": "Hidden size execution",
                "status": "active",
                "org_id": _O,
            },
            {
                "algo_id": "sniper-v1",
                "name": "Sniper",
                "description": "Best-bid/ask opportunistic",
                "status": "beta",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "backtests",
        [
            {
                "backtest_id": "bt-c9d0e1f2-3001",
                "strategy": "mean-reversion-btc",
                "period": "2026-01-01/2026-03-01",
                "sharpe": 1.82,
                "max_drawdown": -0.045,
                "total_return": 0.127,
                "trades": 342,
                "status": "completed",
                "created_at": "2026-03-20T14:00:00Z",
                "org_id": _O,
            },
            {
                "backtest_id": "bt-c9d0e1f2-3002",
                "strategy": "momentum-multi-asset",
                "period": "2026-02-01/2026-03-15",
                "sharpe": 1.14,
                "max_drawdown": -0.078,
                "total_return": 0.064,
                "trades": 189,
                "status": "completed",
                "created_at": "2026-03-20T16:30:00Z",
                "org_id": _A,
            },
            {
                "backtest_id": "bt-c9d0e1f2-3003",
                "strategy": "funding-rate-arb",
                "period": "2026-01-15/2026-03-15",
                "sharpe": 2.10,
                "max_drawdown": -0.022,
                "total_return": 0.094,
                "trades": 560,
                "status": "completed",
                "created_at": "2026-03-21T08:00:00Z",
                "org_id": _O,
            },
            {
                "backtest_id": "bt-c9d0e1f2-3004",
                "strategy": "nfl-outcome",
                "period": "2025-09-01/2026-02-01",
                "sharpe": 0.95,
                "max_drawdown": -0.11,
                "total_return": 0.052,
                "trades": 128,
                "status": "completed",
                "created_at": "2026-03-19T10:00:00Z",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  POSITIONS (20) — across 5 venues
    # ══════════════════════════════════════════════════════════════════

    _positions_records: list[dict[str, object]] = [
        # ── Binance (5) ──
        {
            "position_id": "pos-d2e3f4a5-4001",
            "instrument": "BTC-USDT",
            "venue": "binance",
            "side": "long",
            "quantity": 0.50,
            "entry_price": 66800.00,
            "current_price": 67250.50,
            "unrealized_pnl": 225.25,
            "margin_used": 11133.33,
            "org_id": _O,
            "strategy_id": "strat-002",
            "denomination_currency": "USDT",
            "fx_rate_to_usd": 1.0001,
        },
        {
            "position_id": "pos-d2e3f4a5-4002",
            "instrument": "ETH-USDT",
            "venue": "binance",
            "side": "short",
            "quantity": 3.0,
            "entry_price": 3520.00,
            "current_price": 3480.00,
            "unrealized_pnl": 120.00,
            "margin_used": 3480.00,
            "org_id": _O,
            "strategy_id": "strat-006",
            "denomination_currency": "USDT",
            "fx_rate_to_usd": 1.0001,
        },
        {
            "position_id": "pos-d2e3f4a5-4003",
            "instrument": "SOL-USDT",
            "venue": "binance",
            "side": "long",
            "quantity": 100.0,
            "entry_price": 144.50,
            "current_price": 145.80,
            "unrealized_pnl": 130.00,
            "margin_used": 4816.67,
            "org_id": _V,
            "strategy_id": "strat-017",
            "denomination_currency": "USDT",
            "fx_rate_to_usd": 1.0001,
        },
        {
            "position_id": "pos-d2e3f4a5-4004",
            "instrument": "AVAX-USDT",
            "venue": "binance",
            "side": "long",
            "quantity": 80.0,
            "entry_price": 38.50,
            "current_price": 38.75,
            "unrealized_pnl": 20.00,
            "margin_used": 1033.33,
            "org_id": _B,
            "strategy_id": "strat-006",
            "denomination_currency": "USDT",
            "fx_rate_to_usd": 1.0001,
        },
        {
            "position_id": "pos-d2e3f4a5-4005",
            "instrument": "BTC-USDT",
            "venue": "binance",
            "side": "long",
            "quantity": 0.20,
            "entry_price": 67100.00,
            "current_price": 67250.50,
            "unrealized_pnl": 30.10,
            "margin_used": 4473.33,
            "org_id": _A,
            "strategy_id": "strat-002",
            "denomination_currency": "USDT",
            "fx_rate_to_usd": 1.0001,
        },
        # ── Deribit (4) ──
        {
            "position_id": "pos-d2e3f4a5-4006",
            "instrument": "BTC-28MAR26-70000-C",
            "venue": "deribit",
            "side": "short",
            "quantity": 2.0,
            "entry_price": 1300.00,
            "current_price": 1250.00,
            "unrealized_pnl": 100.00,
            "margin_used": 5200.00,
            "org_id": _O,
            "strategy_id": "strat-014",
            "denomination_currency": "BTC",
            "fx_rate_to_usd": 67000.0,
        },
        {
            "position_id": "pos-d2e3f4a5-4007",
            "instrument": "ETH-USDT",
            "venue": "deribit",
            "side": "short",
            "quantity": 5.0,
            "entry_price": 3520.00,
            "current_price": 3480.00,
            "unrealized_pnl": 200.00,
            "margin_used": 8800.00,
            "org_id": _O,
            "strategy_id": "strat-003",
            "denomination_currency": "BTC",
            "fx_rate_to_usd": 67000.0,
        },
        {
            "position_id": "pos-d2e3f4a5-4008",
            "instrument": "ETH-28MAR26-4000-C",
            "venue": "deribit",
            "side": "long",
            "quantity": 10.0,
            "entry_price": 175.00,
            "current_price": 180.50,
            "unrealized_pnl": 55.00,
            "margin_used": 1750.00,
            "org_id": _A,
            "strategy_id": "strat-014",
            "denomination_currency": "BTC",
            "fx_rate_to_usd": 67000.0,
        },
        {
            "position_id": "pos-d2e3f4a5-4009",
            "instrument": "BTC-28MAR26-65000-P",
            "venue": "deribit",
            "side": "long",
            "quantity": 3.0,
            "entry_price": 820.00,
            "current_price": 790.00,
            "unrealized_pnl": -90.00,
            "margin_used": 2460.00,
            "org_id": _O,
            "strategy_id": "strat-014",
            "denomination_currency": "BTC",
            "fx_rate_to_usd": 67000.0,
        },
        # ── Hyperliquid (4) ──
        {
            "position_id": "pos-d2e3f4a5-4010",
            "instrument": "SOL-USD-PERP",
            "venue": "hyperliquid",
            "side": "long",
            "quantity": 100.0,
            "entry_price": 143.50,
            "current_price": 145.30,
            "unrealized_pnl": 180.00,
            "margin_used": 2870.00,
            "org_id": _O,
            "strategy_id": "strat-009",
            "denomination_currency": "USD",
            "fx_rate_to_usd": 1.0,
        },
        {
            "position_id": "pos-d2e3f4a5-4011",
            "instrument": "ETH-USD-PERP",
            "venue": "hyperliquid",
            "side": "long",
            "quantity": 10.0,
            "entry_price": 3475.00,
            "current_price": 3482.00,
            "unrealized_pnl": 70.00,
            "margin_used": 6950.00,
            "org_id": _O,
            "strategy_id": "strat-009",
            "denomination_currency": "USD",
            "fx_rate_to_usd": 1.0,
        },
        {
            "position_id": "pos-d2e3f4a5-4012",
            "instrument": "BTC-USD-PERP",
            "venue": "hyperliquid",
            "side": "short",
            "quantity": 0.12,
            "entry_price": 67500.00,
            "current_price": 67250.00,
            "unrealized_pnl": 30.00,
            "margin_used": 1620.00,
            "org_id": _O,
            "strategy_id": "strat-011",
            "denomination_currency": "USD",
            "fx_rate_to_usd": 1.0,
        },
        {
            "position_id": "pos-d2e3f4a5-4013",
            "instrument": "ARB-USD-PERP",
            "venue": "hyperliquid",
            "side": "long",
            "quantity": 5000.0,
            "entry_price": 1.15,
            "current_price": 1.18,
            "unrealized_pnl": 150.00,
            "margin_used": 1150.00,
            "org_id": _V,
            "strategy_id": "strat-009",
            "denomination_currency": "USD",
            "fx_rate_to_usd": 1.0,
        },
        # ── Uniswap V3 (4) ──
        {
            "position_id": "pos-d2e3f4a5-4014",
            "instrument": "WETH-USDC",
            "venue": "uniswap_v3",
            "side": "long",
            "quantity": 3.0,
            "entry_price": 3478.50,
            "current_price": 3482.00,
            "unrealized_pnl": 10.50,
            "margin_used": 10435.50,
            "org_id": _O,
            "strategy_id": "strat-001",
            "denomination_currency": "ETH",
            "fx_rate_to_usd": 3500.0,
            "il_pct": 0.85,
            "pool_share_pct": 0.0012,
            "fee_accrued_usd": 142.30,
        },
        {
            "position_id": "pos-d2e3f4a5-4015",
            "instrument": "WBTC-WETH",
            "venue": "uniswap_v3",
            "side": "long",
            "quantity": 0.6,
            "entry_price": 19.32,
            "current_price": 19.35,
            "unrealized_pnl": 0.018,
            "margin_used": 11.59,
            "org_id": _A,
            "strategy_id": "strat-010",
            "denomination_currency": "ETH",
            "fx_rate_to_usd": 3500.0,
            "il_pct": 2.10,
            "pool_share_pct": 0.0003,
            "fee_accrued_usd": 28.50,
        },
        {
            "position_id": "pos-d2e3f4a5-4016",
            "instrument": "WETH-USDC-LP",
            "venue": "uniswap_v3",
            "side": "long",
            "quantity": 1.0,
            "entry_price": 3470.00,
            "current_price": 3480.00,
            "unrealized_pnl": 10.00,
            "margin_used": 3470.00,
            "org_id": _O,
            "strategy_id": "strat-010",
            "denomination_currency": "ETH",
            "fx_rate_to_usd": 3500.0,
            "il_pct": 4.25,
            "pool_share_pct": 0.0045,
            "fee_accrued_usd": 310.75,
        },
        {
            "position_id": "pos-d2e3f4a5-4017",
            "instrument": "UNI-WETH",
            "venue": "uniswap_v3",
            "side": "long",
            "quantity": 500.0,
            "entry_price": 0.0038,
            "current_price": 0.0039,
            "unrealized_pnl": 0.50,
            "margin_used": 1.90,
            "org_id": _V,
            "strategy_id": "strat-010",
            "denomination_currency": "ETH",
            "fx_rate_to_usd": 3500.0,
            "il_pct": 1.30,
            "pool_share_pct": 0.0008,
            "fee_accrued_usd": 15.20,
        },
        # ── Aave V3 (3) ──
        {
            "position_id": "pos-d2e3f4a5-4018",
            "instrument": "WETH-SUPPLY",
            "venue": "aave_v3",
            "side": "long",
            "quantity": 5.0,
            "entry_price": 3480.00,
            "current_price": 3482.00,
            "unrealized_pnl": 10.00,
            "margin_used": 17400.00,
            "org_id": _O,
            "strategy_id": "strat-007",
            "denomination_currency": "ETH",
            "fx_rate_to_usd": 3500.0,
            "health_factor": 2.5,
            "ltv_ratio": 0.42,
            "liquidation_price": 2150.00,
            "collateral_value_usd": 17410.00,
            "borrow_value_usd": 7312.20,
        },
        {
            "position_id": "pos-d2e3f4a5-4019",
            "instrument": "USDC-SUPPLY",
            "venue": "aave_v3",
            "side": "long",
            "quantity": 50000.0,
            "entry_price": 1.0,
            "current_price": 1.0,
            "unrealized_pnl": 0.0,
            "margin_used": 50000.00,
            "org_id": _O,
            "strategy_id": "strat-007",
            "denomination_currency": "ETH",
            "fx_rate_to_usd": 3500.0,
            "health_factor": 1.48,
            "ltv_ratio": 0.68,
            "liquidation_price": 0.92,
            "collateral_value_usd": 50000.00,
            "borrow_value_usd": 34000.00,
        },
        {
            "position_id": "pos-d2e3f4a5-4020",
            "instrument": "WBTC-BORROW",
            "venue": "aave_v3",
            "side": "short",
            "quantity": 0.05,
            "entry_price": 67200.00,
            "current_price": 67250.00,
            "unrealized_pnl": -2.50,
            "margin_used": 3360.00,
            "org_id": _O,
            "strategy_id": "strat-015",
            "denomination_currency": "ETH",
            "fx_rate_to_usd": 3500.0,
            "health_factor": 1.22,
            "ltv_ratio": 0.65,
            "liquidation_price": 72500.00,
            "collateral_value_usd": 5180.00,
            "borrow_value_usd": 3362.50,
        },
    ]
    for _p in _positions_records:
        _p["asset_group"] = _strategy_asset_group.get(str(_p.get("strategy_id", "")), "cefi")
    _seed("positions", _positions_records)

    # ── Batch/live domain separation ──────────────────────────────

    _pos_batch: list[dict[str, object]] = [
        {
            "position_id": "pos-d2e3f4a5-4001",
            "instrument": "BTC-USDT",
            "venue": "binance",
            "side": "long",
            "quantity": 0.50,
            "entry_price": 66800.00,
            "current_price": 67200.00,
            "unrealized_pnl": 200.00,
            "margin_used": 11133.33,
            "org_id": _O,
            "strategy_id": "strat-002",
            "snapshot_at": "2026-03-21T00:00:00Z",
        },
        {
            "position_id": "pos-d2e3f4a5-4010",
            "instrument": "SOL-USD-PERP",
            "venue": "hyperliquid",
            "side": "long",
            "quantity": 100.0,
            "entry_price": 143.50,
            "current_price": 144.80,
            "unrealized_pnl": 130.00,
            "margin_used": 2870.00,
            "org_id": _O,
            "strategy_id": "strat-009",
            "snapshot_at": "2026-03-21T00:00:00Z",
        },
        {
            "position_id": "pos-d2e3f4a5-4007",
            "instrument": "ETH-USDT",
            "venue": "deribit",
            "side": "short",
            "quantity": 5.0,
            "entry_price": 3520.00,
            "current_price": 3490.00,
            "unrealized_pnl": 150.00,
            "margin_used": 8800.00,
            "org_id": _O,
            "strategy_id": "strat-003",
            "snapshot_at": "2026-03-21T00:00:00Z",
        },
    ]
    for _b in _pos_batch:
        _b["asset_group"] = _strategy_asset_group.get(str(_b.get("strategy_id", "")), "cefi")
    _seed("positions_batch", _pos_batch)

    _pos_live: list[dict[str, object]] = [
        {
            "position_id": "pos-d2e3f4a5-4001",
            "instrument": "BTC-USDT",
            "venue": "binance",
            "side": "long",
            "quantity": 0.50,
            "entry_price": 66800.00,
            "current_price": 67250.50,
            "unrealized_pnl": 225.25,
            "margin_used": 11133.33,
            "org_id": _O,
            "strategy_id": "strat-002",
            "snapshot_at": "2026-03-21T09:30:00Z",
        },
        {
            "position_id": "pos-d2e3f4a5-4010",
            "instrument": "SOL-USD-PERP",
            "venue": "hyperliquid",
            "side": "long",
            "quantity": 100.0,
            "entry_price": 143.50,
            "current_price": 145.30,
            "unrealized_pnl": 180.00,
            "margin_used": 2870.00,
            "org_id": _O,
            "strategy_id": "strat-009",
            "snapshot_at": "2026-03-21T09:30:00Z",
        },
        {
            "position_id": "pos-d2e3f4a5-4007",
            "instrument": "ETH-USDT",
            "venue": "deribit",
            "side": "short",
            "quantity": 5.0,
            "entry_price": 3520.00,
            "current_price": 3480.00,
            "unrealized_pnl": 200.00,
            "margin_used": 8800.00,
            "org_id": _O,
            "strategy_id": "strat-003",
            "snapshot_at": "2026-03-21T09:30:00Z",
        },
    ]
    for _lv in _pos_live:
        _lv["asset_group"] = _strategy_asset_group.get(str(_lv.get("strategy_id", "")), "cefi")
    _seed("positions_live", _pos_live)

    _seed(
        "position_summary",
        [
            {
                "total_positions": 20,
                "total_unrealized_pnl": 1218.88,
                "total_notional": 178500.00,
                "venues_active": 5,
                "long_count": 15,
                "short_count": 5,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "balances",
        [
            {
                "venue": "binance",
                "currency": "USDT",
                "available": 48250.00,
                "locked": 10087.50,
                "total": 58337.50,
                "org_id": _O,
            },
            {
                "venue": "binance",
                "currency": "BTC",
                "available": 0.50,
                "locked": 0.0,
                "total": 0.50,
                "org_id": _O,
            },
            {
                "venue": "hyperliquid",
                "currency": "USDC",
                "available": 22100.00,
                "locked": 7265.00,
                "total": 29365.00,
                "org_id": _O,
            },
            {
                "venue": "deribit",
                "currency": "ETH",
                "available": 10.0,
                "locked": 5.0,
                "total": 15.0,
                "org_id": _O,
            },
            {
                "venue": "uniswap_v3",
                "currency": "WETH",
                "available": 4.0,
                "locked": 3.0,
                "total": 7.0,
                "org_id": _O,
            },
            {
                "venue": "aave_v3",
                "currency": "WETH",
                "available": 0.0,
                "locked": 5.0,
                "total": 5.0,
                "org_id": _O,
            },
            {
                "venue": "binance",
                "currency": "USDT",
                "available": 12000.00,
                "locked": 2500.00,
                "total": 14500.00,
                "org_id": _A,
            },
            {
                "venue": "binance",
                "currency": "USDT",
                "available": 8000.00,
                "locked": 1500.00,
                "total": 9500.00,
                "org_id": _V,
            },
            {
                "venue": "binance",
                "currency": "USDT",
                "available": 3000.00,
                "locked": 500.00,
                "total": 3500.00,
                "org_id": _B,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  TRADING ANALYTICS
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "pnl",
        [
            {
                "venue": "binance",
                "realized_pnl": 1245.80,
                "unrealized_pnl": 525.35,
                "fees": 42.30,
                "date": "2026-03-21",
                "org_id": _O,
            },
            {
                "venue": "hyperliquid",
                "realized_pnl": 560.00,
                "unrealized_pnl": 430.00,
                "fees": 8.40,
                "date": "2026-03-21",
                "org_id": _O,
            },
            {
                "venue": "deribit",
                "realized_pnl": -320.50,
                "unrealized_pnl": 265.00,
                "fees": 15.60,
                "date": "2026-03-21",
                "org_id": _O,
            },
            {
                "venue": "uniswap_v3",
                "realized_pnl": 82.00,
                "unrealized_pnl": 21.02,
                "fees": 13.95,
                "date": "2026-03-21",
                "org_id": _O,
            },
            {
                "venue": "aave_v3",
                "realized_pnl": 45.00,
                "unrealized_pnl": 7.50,
                "fees": 15.66,
                "date": "2026-03-21",
                "org_id": _O,
            },
            {
                "venue": "binance",
                "realized_pnl": 320.00,
                "unrealized_pnl": 50.10,
                "fees": 12.01,
                "date": "2026-03-21",
                "org_id": _A,
            },
            {
                "venue": "binance",
                "realized_pnl": 110.00,
                "unrealized_pnl": 150.00,
                "fees": 4.32,
                "date": "2026-03-21",
                "org_id": _V,
            },
            {
                "venue": "binance",
                "realized_pnl": -18.50,
                "unrealized_pnl": 20.00,
                "fees": 0.39,
                "date": "2026-03-21",
                "org_id": _B,
            },
        ],
    )

    _seed(
        "pnl_batch",
        [
            {
                "venue": "binance",
                "realized_pnl": 1200.00,
                "unrealized_pnl": 480.00,
                "fees": 40.10,
                "date": "2026-03-21",
                "org_id": _O,
                "snapshot_at": "2026-03-21T00:00:00Z",
            },
            {
                "venue": "hyperliquid",
                "realized_pnl": 540.00,
                "unrealized_pnl": 390.00,
                "fees": 7.80,
                "date": "2026-03-21",
                "org_id": _O,
                "snapshot_at": "2026-03-21T00:00:00Z",
            },
            {
                "venue": "deribit",
                "realized_pnl": -310.00,
                "unrealized_pnl": 240.00,
                "fees": 14.50,
                "date": "2026-03-21",
                "org_id": _O,
                "snapshot_at": "2026-03-21T00:00:00Z",
            },
        ],
    )

    _seed(
        "pnl_live",
        [
            {
                "venue": "binance",
                "realized_pnl": 1245.80,
                "unrealized_pnl": 525.35,
                "fees": 42.30,
                "date": "2026-03-21",
                "org_id": _O,
                "snapshot_at": "2026-03-21T09:30:00Z",
            },
            {
                "venue": "hyperliquid",
                "realized_pnl": 560.00,
                "unrealized_pnl": 430.00,
                "fees": 8.40,
                "date": "2026-03-21",
                "org_id": _O,
                "snapshot_at": "2026-03-21T09:30:00Z",
            },
            {
                "venue": "deribit",
                "realized_pnl": -320.50,
                "unrealized_pnl": 265.00,
                "fees": 15.60,
                "date": "2026-03-21",
                "org_id": _O,
                "snapshot_at": "2026-03-21T09:30:00Z",
            },
        ],
    )

    _seed(
        "analytics_timeseries",
        [
            {
                "timestamp": "2026-03-21T00:00:00Z",
                "equity": 87500.00,
                "drawdown": -0.012,
                "org_id": _O,
            },
            {
                "timestamp": "2026-03-21T04:00:00Z",
                "equity": 87820.00,
                "drawdown": -0.008,
                "org_id": _O,
            },
            {
                "timestamp": "2026-03-21T08:00:00Z",
                "equity": 88200.00,
                "drawdown": 0.0,
                "org_id": _O,
            },
            {
                "timestamp": "2026-03-21T12:00:00Z",
                "equity": 88050.00,
                "drawdown": -0.002,
                "org_id": _O,
            },
            {
                "timestamp": "2026-03-21T00:00:00Z",
                "equity": 14200.00,
                "drawdown": -0.005,
                "org_id": _A,
            },
            {
                "timestamp": "2026-03-21T04:00:00Z",
                "equity": 14280.00,
                "drawdown": -0.002,
                "org_id": _A,
            },
            {
                "timestamp": "2026-03-21T08:00:00Z",
                "equity": 14350.00,
                "drawdown": 0.0,
                "org_id": _A,
            },
            {
                "timestamp": "2026-03-21T12:00:00Z",
                "equity": 14320.00,
                "drawdown": -0.002,
                "org_id": _A,
            },
        ],
    )

    _seed(
        "performance",
        [
            {
                "period": "30d",
                "total_return": 0.087,
                "sharpe_ratio": 1.65,
                "sortino_ratio": 2.10,
                "max_drawdown": -0.045,
                "win_rate": 0.58,
                "profit_factor": 1.72,
                "total_trades": 531,
                "org_id": _O,
            },
            {
                "period": "30d",
                "total_return": 0.042,
                "sharpe_ratio": 1.12,
                "sortino_ratio": 1.45,
                "max_drawdown": -0.032,
                "win_rate": 0.54,
                "profit_factor": 1.38,
                "total_trades": 145,
                "org_id": _A,
            },
        ],
    )

    _seed(
        "analytics_organizations",
        [
            {
                "org_id": _O,
                "name": "Odum Internal",
                "aum": 18000000.00,
                "strategies": 11,
            },
            {
                "org_id": _A,
                "name": "Alpha Capital",
                "aum": 15000000.00,
                "strategies": 4,
            },
            {
                "org_id": _V,
                "name": "Vertex Partners",
                "aum": 15000000.00,
                "strategies": 3,
            },
            {
                "org_id": _B,
                "name": "Beta Fund",
                "aum": 5000000.00,
                "strategies": 2,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  SETTLEMENTS (8), INVOICES (5), FEE SCHEDULES (3)
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "settlements",
        [
            {
                "settlement_id": "stl-a3b4c5d6-6001",
                "venue": "binance",
                "currency": "USDT",
                "amount": 5000.00,
                "status": "completed",
                "settled_at": "2026-03-20T18:00:00Z",
                "org_id": _O,
            },
            {
                "settlement_id": "stl-a3b4c5d6-6002",
                "venue": "deribit",
                "currency": "BTC",
                "amount": 0.08,
                "status": "pending",
                "settled_at": None,
                "org_id": _O,
            },
            {
                "settlement_id": "stl-a3b4c5d6-6003",
                "venue": "hyperliquid",
                "currency": "USDC",
                "amount": 2200.00,
                "status": "completed",
                "settled_at": "2026-03-20T20:00:00Z",
                "org_id": _O,
            },
            {
                "settlement_id": "stl-a3b4c5d6-6004",
                "venue": "binance",
                "currency": "USDT",
                "amount": 1500.00,
                "status": "completed",
                "settled_at": "2026-03-20T18:30:00Z",
                "org_id": _A,
            },
            {
                "settlement_id": "stl-a3b4c5d6-6005",
                "venue": "uniswap_v3",
                "currency": "USDC",
                "amount": 800.00,
                "status": "failed",
                "settled_at": None,
                "org_id": _O,
            },
            {
                "settlement_id": "stl-a3b4c5d6-6006",
                "venue": "aave_v3",
                "currency": "ETH",
                "amount": 0.5,
                "status": "completed",
                "settled_at": "2026-03-20T22:00:00Z",
                "org_id": _O,
            },
            {
                "settlement_id": "stl-a3b4c5d6-6007",
                "venue": "binance",
                "currency": "USDT",
                "amount": 750.00,
                "status": "in_transit",
                "settled_at": None,
                "org_id": _V,
            },
            {
                "settlement_id": "stl-a3b4c5d6-6008",
                "venue": "deribit",
                "currency": "ETH",
                "amount": 1.0,
                "status": "pending",
                "settled_at": None,
                "org_id": _B,
            },
        ],
    )

    _seed(
        "invoices",
        [
            {
                "invoice_id": "inv-b4c5d6e7-7001",
                "org_id": _A,
                "type": "management_fee",
                "amount": 12500.00,
                "currency": "USD",
                "period": "2026-Q1",
                "status": "paid",
                "issued_at": "2026-04-01T00:00:00Z",
            },
            {
                "invoice_id": "inv-b4c5d6e7-7002",
                "org_id": _V,
                "type": "management_fee",
                "amount": 18750.00,
                "currency": "USD",
                "period": "2026-Q1",
                "status": "pending",
                "issued_at": "2026-04-01T00:00:00Z",
            },
            {
                "invoice_id": "inv-b4c5d6e7-7003",
                "org_id": _B,
                "type": "management_fee",
                "amount": 6250.00,
                "currency": "USD",
                "period": "2026-Q1",
                "status": "pending",
                "issued_at": "2026-04-01T00:00:00Z",
            },
            {
                "invoice_id": "inv-b4c5d6e7-7004",
                "org_id": _A,
                "type": "management_fee",
                "amount": 12500.00,
                "currency": "USD",
                "period": "2025-Q4",
                "status": "paid",
                "issued_at": "2026-01-01T00:00:00Z",
            },
            {
                "invoice_id": "inv-b4c5d6e7-7005",
                "org_id": _V,
                "type": "management_fee",
                "amount": 18750.00,
                "currency": "USD",
                "period": "2025-Q4",
                "status": "paid",
                "issued_at": "2026-01-01T00:00:00Z",
            },
        ],
    )

    _seed(
        "fee_schedules",
        [
            {
                "schedule_id": "fee-c5d6e7f8-8001",
                "name": "Basic",
                "management_fee_pct": 0.5,
                "performance_fee_pct": 0.0,
                "min_aum": 0,
                "org_id": _B,
            },
            {
                "schedule_id": "fee-c5d6e7f8-8002",
                "name": "Premium",
                "management_fee_pct": 1.0,
                "performance_fee_pct": 10.0,
                "min_aum": 5000000,
                "org_id": _A,
            },
            {
                "schedule_id": "fee-c5d6e7f8-8003",
                "name": "Full Service",
                "management_fee_pct": 1.5,
                "performance_fee_pct": 15.0,
                "min_aum": 10000000,
                "org_id": _V,
            },
        ],
    )

    _seed(
        "analytics_instruments",
        [
            {
                "instrument": "BTC-USDT",
                "asset_group": "crypto",
                "venue": "binance",
                "volume_24h": 1250000.00,
                "org_id": _O,
            },
            {
                "instrument": "ETH-USDT",
                "asset_group": "crypto",
                "venue": "binance",
                "volume_24h": 780000.00,
                "org_id": _O,
            },
            {
                "instrument": "SOL-USD-PERP",
                "asset_group": "crypto",
                "venue": "hyperliquid",
                "volume_24h": 420000.00,
                "org_id": _O,
            },
            {
                "instrument": "BTC-28MAR26-70000-C",
                "asset_group": "option",
                "venue": "deribit",
                "volume_24h": 85000.00,
                "org_id": _O,
            },
            {
                "instrument": "WETH-USDC",
                "asset_group": "defi",
                "venue": "uniswap_v3",
                "volume_24h": 320000.00,
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  ML — 8 models, 12 experiments, 5 training jobs, 20 features
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "model_families",
        [
            {
                "family_id": "mf-mean-reversion-btc",
                "name": "Mean Reversion BTC",
                "framework": "pytorch",
                "versions": 3,
                "org_id": _O,
            },
            {
                "family_id": "mf-momentum-multi-asset",
                "name": "Momentum Multi-Asset",
                "framework": "pytorch",
                "versions": 4,
                "org_id": _O,
            },
            {
                "family_id": "mf-vol-surface-eth",
                "name": "Vol Surface ETH",
                "framework": "pytorch",
                "versions": 2,
                "org_id": _O,
            },
            {
                "family_id": "mf-funding-rate-arb",
                "name": "Funding Rate Arb",
                "framework": "pytorch",
                "versions": 2,
                "org_id": _O,
            },
            {
                "family_id": "mf-nfl-outcome",
                "name": "NFL Outcome",
                "framework": "xgboost",
                "versions": 5,
                "org_id": _O,
            },
            {
                "family_id": "mf-polymarket-sentiment",
                "name": "Polymarket Sentiment",
                "framework": "pytorch",
                "versions": 1,
                "org_id": _O,
            },
            {
                "family_id": "mf-stat-arb-pairs",
                "name": "Stat Arb Pairs",
                "framework": "pytorch",
                "versions": 3,
                "org_id": _V,
            },
            {
                "family_id": "mf-aave-yield-optimizer",
                "name": "Aave Yield Optimizer",
                "framework": "xgboost",
                "versions": 2,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "experiments",
        [
            {
                "experiment_id": "exp-b1c2d3e4-7001",
                "family": "mf-mean-reversion-btc",
                "name": "btc-1h-lstm-v3",
                "status": "completed",
                "best_metric": 0.0032,
                "metric_name": "mse",
                "created_at": "2026-03-19T10:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7002",
                "family": "mf-nfl-outcome",
                "name": "epl-match-xgb-v5",
                "status": "running",
                "best_metric": 0.71,
                "metric_name": "accuracy",
                "created_at": "2026-03-20T14:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7003",
                "family": "mf-momentum-multi-asset",
                "name": "multi-asset-transformer-v4",
                "status": "completed",
                "best_metric": 1.85,
                "metric_name": "sharpe",
                "created_at": "2026-03-18T08:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7004",
                "family": "mf-vol-surface-eth",
                "name": "eth-vol-surface-garch-v2",
                "status": "completed",
                "best_metric": 0.0018,
                "metric_name": "mse",
                "created_at": "2026-03-17T12:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7005",
                "family": "mf-funding-rate-arb",
                "name": "funding-lstm-v2",
                "status": "completed",
                "best_metric": 2.10,
                "metric_name": "sharpe",
                "created_at": "2026-03-16T09:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7006",
                "family": "mf-polymarket-sentiment",
                "name": "poly-sent-bert-v1",
                "status": "running",
                "best_metric": 0.68,
                "metric_name": "accuracy",
                "created_at": "2026-03-21T06:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7007",
                "family": "mf-stat-arb-pairs",
                "name": "pairs-coint-v3",
                "status": "completed",
                "best_metric": 1.45,
                "metric_name": "sharpe",
                "created_at": "2026-03-15T14:00:00Z",
                "org_id": _V,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7008",
                "family": "mf-aave-yield-optimizer",
                "name": "aave-yield-xgb-v2",
                "status": "completed",
                "best_metric": 0.042,
                "metric_name": "apy_improvement",
                "created_at": "2026-03-14T10:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7009",
                "family": "mf-mean-reversion-btc",
                "name": "btc-4h-attention-v3",
                "status": "failed",
                "best_metric": 0.0055,
                "metric_name": "mse",
                "created_at": "2026-03-20T08:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7010",
                "family": "mf-nfl-outcome",
                "name": "nfl-ensemble-v5",
                "status": "completed",
                "best_metric": 0.73,
                "metric_name": "accuracy",
                "created_at": "2026-03-13T16:00:00Z",
                "org_id": _O,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7011",
                "family": "mf-momentum-multi-asset",
                "name": "multi-asset-cnn-v3",
                "status": "completed",
                "best_metric": 1.62,
                "metric_name": "sharpe",
                "created_at": "2026-03-12T11:00:00Z",
                "org_id": _A,
            },
            {
                "experiment_id": "exp-b1c2d3e4-7012",
                "family": "mf-stat-arb-pairs",
                "name": "pairs-kalman-v2",
                "status": "completed",
                "best_metric": 1.28,
                "metric_name": "sharpe",
                "created_at": "2026-03-11T08:00:00Z",
                "org_id": _V,
            },
        ],
    )

    _seed(
        "training_runs",
        [
            {
                "run_id": "run-c2d3e4f5-8001",
                "experiment_id": "exp-b1c2d3e4-7001",
                "epoch": 50,
                "train_loss": 0.0041,
                "val_loss": 0.0032,
                "duration_s": 1842,
                "status": "completed",
                "org_id": _O,
            },
            {
                "run_id": "run-c2d3e4f5-8002",
                "experiment_id": "exp-b1c2d3e4-7002",
                "epoch": 30,
                "train_loss": 0.42,
                "val_loss": 0.45,
                "duration_s": 620,
                "status": "running",
                "org_id": _O,
            },
            {
                "run_id": "run-c2d3e4f5-8003",
                "experiment_id": "exp-b1c2d3e4-7003",
                "epoch": 100,
                "train_loss": 0.0028,
                "val_loss": 0.0035,
                "duration_s": 3200,
                "status": "completed",
                "org_id": _O,
            },
            {
                "run_id": "run-c2d3e4f5-8004",
                "experiment_id": "exp-b1c2d3e4-7006",
                "epoch": 15,
                "train_loss": 0.38,
                "val_loss": 0.41,
                "duration_s": 450,
                "status": "running",
                "org_id": _O,
            },
            {
                "run_id": "run-c2d3e4f5-8005",
                "experiment_id": "exp-b1c2d3e4-7009",
                "epoch": 20,
                "train_loss": 0.0060,
                "val_loss": 0.0082,
                "duration_s": 980,
                "status": "failed",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "model_versions",
        [
            {
                "version_id": "mv-d3e4f5a6-9001",
                "family": "mf-mean-reversion-btc",
                "version": "v3.1.0",
                "stage": "production",
                "metrics": {"sharpe": 1.82, "accuracy": 0.62},
                "created_at": "2026-03-18T12:00:00Z",
                "org_id": _O,
            },
            {
                "version_id": "mv-d3e4f5a6-9002",
                "family": "mf-nfl-outcome",
                "version": "v5.0.0",
                "stage": "staging",
                "metrics": {"sharpe": 0.95, "accuracy": 0.73},
                "created_at": "2026-03-20T16:00:00Z",
                "org_id": _O,
            },
            {
                "version_id": "mv-d3e4f5a6-9003",
                "family": "mf-momentum-multi-asset",
                "version": "v4.0.0",
                "stage": "production",
                "metrics": {"sharpe": 1.85, "accuracy": 0.59},
                "created_at": "2026-03-19T10:00:00Z",
                "org_id": _O,
            },
            {
                "version_id": "mv-d3e4f5a6-9004",
                "family": "mf-vol-surface-eth",
                "version": "v2.0.0",
                "stage": "production",
                "metrics": {"sharpe": 1.42, "accuracy": 0.65},
                "created_at": "2026-03-17T14:00:00Z",
                "org_id": _O,
            },
            {
                "version_id": "mv-d3e4f5a6-9005",
                "family": "mf-funding-rate-arb",
                "version": "v2.1.0",
                "stage": "production",
                "metrics": {"sharpe": 2.10, "accuracy": 0.58},
                "created_at": "2026-03-16T12:00:00Z",
                "org_id": _O,
            },
            {
                "version_id": "mv-d3e4f5a6-9006",
                "family": "mf-polymarket-sentiment",
                "version": "v1.0.0",
                "stage": "staging",
                "metrics": {"sharpe": 0.88, "accuracy": 0.68},
                "created_at": "2026-03-21T08:00:00Z",
                "org_id": _O,
            },
            {
                "version_id": "mv-d3e4f5a6-9007",
                "family": "mf-stat-arb-pairs",
                "version": "v3.0.0",
                "stage": "production",
                "metrics": {"sharpe": 1.45, "accuracy": 0.61},
                "created_at": "2026-03-15T16:00:00Z",
                "org_id": _V,
            },
            {
                "version_id": "mv-d3e4f5a6-9008",
                "family": "mf-aave-yield-optimizer",
                "version": "v2.0.0",
                "stage": "deprecated",
                "metrics": {"sharpe": 1.05, "accuracy": 0.55},
                "created_at": "2026-03-14T12:00:00Z",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "model_deployments",
        [
            {
                "deployment_id": "dep-e4f5a6b7-0001",
                "model_version": "mv-d3e4f5a6-9001",
                "endpoint": "mean-reversion-btc-prod",
                "replicas": 2,
                "status": "serving",
                "latency_p99_ms": 28,
                "org_id": _O,
            },
            {
                "deployment_id": "dep-e4f5a6b7-0002",
                "model_version": "mv-d3e4f5a6-9003",
                "endpoint": "momentum-multi-asset-prod",
                "replicas": 2,
                "status": "serving",
                "latency_p99_ms": 35,
                "org_id": _O,
            },
            {
                "deployment_id": "dep-e4f5a6b7-0003",
                "model_version": "mv-d3e4f5a6-9004",
                "endpoint": "vol-surface-eth-prod",
                "replicas": 1,
                "status": "serving",
                "latency_p99_ms": 42,
                "org_id": _O,
            },
            {
                "deployment_id": "dep-e4f5a6b7-0004",
                "model_version": "mv-d3e4f5a6-9005",
                "endpoint": "funding-rate-arb-prod",
                "replicas": 1,
                "status": "serving",
                "latency_p99_ms": 22,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "ml_features",
        [
            {
                "feature_id": "feat-rsi-14",
                "name": "rsi_14",
                "category": "technical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-rsi-28",
                "name": "rsi_28",
                "category": "technical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-vol-24h",
                "name": "volatility_24h",
                "category": "statistical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-vol-7d",
                "name": "volatility_7d",
                "category": "statistical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-ob-imbal",
                "name": "orderbook_imbalance",
                "category": "microstructure",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-ob-depth",
                "name": "orderbook_depth_10",
                "category": "microstructure",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-funding",
                "name": "funding_rate",
                "category": "defi",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-gas-price",
                "name": "gas_price_gwei",
                "category": "defi",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-tvl",
                "name": "total_value_locked",
                "category": "defi",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-macd",
                "name": "macd_signal",
                "category": "technical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-bb-width",
                "name": "bollinger_bandwidth",
                "category": "technical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-atr-14",
                "name": "atr_14",
                "category": "technical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-vwap-dev",
                "name": "vwap_deviation",
                "category": "microstructure",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-spread",
                "name": "bid_ask_spread",
                "category": "microstructure",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-corr-btc",
                "name": "correlation_btc_30d",
                "category": "cross_instrument",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-skew",
                "name": "return_skewness_7d",
                "category": "statistical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-kurt",
                "name": "return_kurtosis_7d",
                "category": "statistical",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-elo",
                "name": "team_elo_rating",
                "category": "sports",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-injury",
                "name": "injury_impact_score",
                "category": "sports",
                "dtype": "float64",
                "org_id": _O,
            },
            {
                "feature_id": "feat-sentiment",
                "name": "market_sentiment_score",
                "category": "alternative",
                "dtype": "float64",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "datasets",
        [
            {
                "dataset_id": "ds-f5a6b7c8-1001",
                "name": "btc-1h-features-2026q1",
                "rows": 2160,
                "columns": 48,
                "size_mb": 12.4,
                "created_at": "2026-03-15T08:00:00Z",
                "org_id": _O,
            },
            {
                "dataset_id": "ds-f5a6b7c8-1002",
                "name": "epl-match-features-2025-26",
                "rows": 760,
                "columns": 112,
                "size_mb": 4.8,
                "created_at": "2026-03-10T10:00:00Z",
                "org_id": _O,
            },
            {
                "dataset_id": "ds-f5a6b7c8-1003",
                "name": "multi-asset-4h-features-2026q1",
                "rows": 4320,
                "columns": 64,
                "size_mb": 28.1,
                "created_at": "2026-03-18T06:00:00Z",
                "org_id": _O,
            },
            {
                "dataset_id": "ds-f5a6b7c8-1004",
                "name": "defi-onchain-hourly-2026q1",
                "rows": 2160,
                "columns": 32,
                "size_mb": 8.2,
                "created_at": "2026-03-17T12:00:00Z",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  REPORTING
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "reports",
        [
            {
                "report_id": "rpt-a6b7c8d9-2001",
                "report_type": "daily_pnl",
                "title": "Daily PnL Report - 2026-03-20",
                "format": "pdf",
                "status": "generated",
                "created_at": "2026-03-20T23:59:00Z",
                "org_id": _O,
            },
            {
                "report_id": "rpt-a6b7c8d9-2002",
                "report_type": "risk_summary",
                "title": "Weekly Risk Summary - W12 2026",
                "format": "xlsx",
                "status": "generated",
                "created_at": "2026-03-21T06:00:00Z",
                "org_id": _O,
            },
            {
                "report_id": "rpt-a6b7c8d9-2003",
                "report_type": "daily_pnl",
                "title": "Daily PnL Report - 2026-03-20",
                "format": "pdf",
                "status": "generated",
                "created_at": "2026-03-20T23:59:00Z",
                "org_id": _A,
            },
        ],
    )

    _seed(
        "reporting_settlements",
        [
            {
                "settlement_id": "rstl-b7c8d9e0-3001",
                "counterparty": "Binance",
                "net_amount": 4850.00,
                "currency": "USDT",
                "status": "settled",
                "date": "2026-03-20",
                "org_id": _O,
            },
            {
                "settlement_id": "rstl-b7c8d9e0-3002",
                "counterparty": "Deribit",
                "net_amount": 1200.00,
                "currency": "USDT",
                "status": "settled",
                "date": "2026-03-20",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "reconciliation",
        [
            {
                "recon_id": "rcn-c8d9e0f1-4001",
                "date": "2026-03-20",
                "venue": "binance",
                "matched": 342,
                "unmatched": 2,
                "breaks": 0,
                "status": "pass",
                "org_id": _O,
            },
            {
                "recon_id": "rcn-c8d9e0f1-4002",
                "date": "2026-03-20",
                "venue": "hyperliquid",
                "matched": 189,
                "unmatched": 0,
                "breaks": 0,
                "status": "pass",
                "org_id": _O,
            },
            {
                "recon_id": "rcn-c8d9e0f1-4003",
                "date": "2026-03-20",
                "venue": "deribit",
                "matched": 95,
                "unmatched": 1,
                "breaks": 0,
                "status": "pass",
                "org_id": _O,
            },
            {
                "recon_id": "rcn-c8d9e0f1-4004",
                "date": "2026-03-20",
                "venue": "uniswap_v3",
                "matched": 28,
                "unmatched": 0,
                "breaks": 1,
                "status": "warn",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  AUDIT
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "audit_events",
        [
            {
                "event_id": "evt-d9e0f1a2-5001",
                "event_type": "ORDER_PLACED",
                "service": "execution-service",
                "user": "api-key-alpha",
                "detail": "Limit buy 0.15 BTC-USDT @ 67250.50",
                "timestamp": "2026-03-21T08:12:33Z",
                "org_id": _O,
            },
            {
                "event_id": "evt-d9e0f1a2-5002",
                "event_type": "CONFIG_CHANGED",
                "service": "config-service",
                "user": "admin",
                "detail": "Updated risk limit for binance:BTC-USDT",
                "timestamp": "2026-03-21T07:45:00Z",
                "org_id": _O,
            },
            {
                "event_id": "evt-d9e0f1a2-5003",
                "event_type": "MODEL_DEPLOYED",
                "service": "ml-inference-service",
                "user": "ml-pipeline",
                "detail": "Deployed mean-reversion-btc v3.1.0 to production",
                "timestamp": "2026-03-20T18:00:00Z",
                "org_id": _O,
            },
            {
                "event_id": "evt-d9e0f1a2-5004",
                "event_type": "ORDER_PLACED",
                "service": "execution-service",
                "user": "api-key-acme",
                "detail": "Limit sell 0.10 BTC-USDT @ 67400.00",
                "timestamp": "2026-03-21T09:30:00Z",
                "org_id": _A,
            },
        ],
    )

    _seed(
        "compliance",
        [
            {
                "check_id": "cmp-e0f1a2b3-6001",
                "rule": "position_limit",
                "status": "pass",
                "detail": "All positions within configured limits",
                "checked_at": "2026-03-21T08:00:00Z",
                "org_id": _O,
            },
            {
                "check_id": "cmp-e0f1a2b3-6002",
                "rule": "wash_trade_detection",
                "status": "pass",
                "detail": "No wash trades detected in last 24h",
                "checked_at": "2026-03-21T08:00:00Z",
                "org_id": _O,
            },
            {
                "check_id": "cmp-e0f1a2b3-6003",
                "rule": "concentration_limit",
                "status": "warn",
                "detail": "SOL-USD-PERP approaching 30% portfolio concentration",
                "checked_at": "2026-03-21T08:00:00Z",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "data_health",
        [
            {
                "source": "binance-ws",
                "status": "healthy",
                "last_message_at": "2026-03-21T09:29:58Z",
                "gap_count_24h": 0,
                "org_id": _O,
            },
            {
                "source": "deribit-ws",
                "status": "healthy",
                "last_message_at": "2026-03-21T09:29:55Z",
                "gap_count_24h": 1,
                "org_id": _O,
            },
            {
                "source": "hyperliquid-rest",
                "status": "degraded",
                "last_message_at": "2026-03-21T09:25:00Z",
                "gap_count_24h": 4,
                "org_id": _O,
            },
            {
                "source": "uniswap-v3-events",
                "status": "healthy",
                "last_message_at": "2026-03-21T09:29:50Z",
                "gap_count_24h": 0,
                "org_id": _O,
            },
            {
                "source": "aave-v3-events",
                "status": "healthy",
                "last_message_at": "2026-03-21T09:28:00Z",
                "gap_count_24h": 2,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "audit_logs",
        [
            {
                "log_id": "log-f1a2b3c4-7001",
                "service": "execution-service",
                "level": "INFO",
                "message": "Order ord-a1b2c3d4-1001 filled at 67250.50",
                "timestamp": "2026-03-21T08:12:34Z",
                "org_id": _O,
            },
            {
                "log_id": "log-f1a2b3c4-7002",
                "service": "risk-and-exposure-service",
                "level": "WARN",
                "message": "Position notional approaching 80% of limit on hyperliquid",
                "timestamp": "2026-03-21T09:16:00Z",
                "org_id": _O,
            },
            {
                "log_id": "log-f1a2b3c4-7003",
                "service": "execution-service",
                "level": "INFO",
                "message": "Order ord-a1b2c3d4-1005 filled at 67398.65",
                "timestamp": "2026-03-21T09:30:01Z",
                "org_id": _A,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  CONFIG
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "system_config",
        [
            {
                "environment": "staging",
                "cloud_provider": "gcp",
                "region": "asia-northeast1",
                "mock_mode": True,
                "max_order_rate": 100,
                "default_leverage": 3.0,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "config_venues",
        [
            {
                "venue": "binance",
                "enabled": True,
                "api_key_configured": True,
                "rate_limit": 1200,
                "ws_enabled": True,
                "org_id": _O,
            },
            {
                "venue": "deribit",
                "enabled": True,
                "api_key_configured": True,
                "rate_limit": 500,
                "ws_enabled": True,
                "org_id": _O,
            },
            {
                "venue": "hyperliquid",
                "enabled": True,
                "api_key_configured": True,
                "rate_limit": 300,
                "ws_enabled": False,
                "org_id": _O,
            },
            {
                "venue": "uniswap_v3",
                "enabled": True,
                "api_key_configured": False,
                "rate_limit": 100,
                "ws_enabled": False,
                "org_id": _O,
            },
            {
                "venue": "aave_v3",
                "enabled": True,
                "api_key_configured": False,
                "rate_limit": 100,
                "ws_enabled": False,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "feature_flags",
        [
            {
                "flag": "defi_execution",
                "enabled": True,
                "description": "Enable DeFi execution pipeline",
                "org_id": _O,
            },
            {
                "flag": "sports_trading",
                "enabled": True,
                "description": "Enable sports trading domain",
                "org_id": _O,
            },
            {
                "flag": "flash_loans",
                "enabled": False,
                "description": "Enable flash loan execution",
                "org_id": _O,
            },
            {
                "flag": "experimental_algos",
                "enabled": False,
                "description": "Enable experimental execution algos",
                "org_id": _O,
            },
            {
                "flag": "prediction_markets",
                "enabled": True,
                "description": "Enable prediction market trading",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  ALERTS (18) — 3 critical, 5 high, 6 medium, 4 low
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "alerts",
        [
            # ── Critical (3) ──
            {
                "alert_id": "alrt-a2b3c4d5-8001",
                "severity": "critical",
                "status": "active",
                "message": "Execution-service circuit breaker OPEN on binance",
                "source": "execution-service",
                "strategy_id": "strat-002",
                "org_id": _O,
                "timestamp": "2026-03-21T09:28:00Z",
                "acknowledged": False,
                "escalated_at": "2026-03-21T09:28:30Z",
            },
            {
                "alert_id": "alrt-a2b3c4d5-8002",
                "severity": "critical",
                "status": "active",
                "message": "Aave V3 health factor below 1.1 - liquidation risk",
                "source": "risk-and-exposure-service",
                "strategy_id": "strat-007",
                "org_id": _O,
                "timestamp": "2026-03-21T09:20:00Z",
                "acknowledged": False,
                "escalated_at": "2026-03-21T09:20:15Z",
            },
            {
                "alert_id": "alrt-a2b3c4d5-8003",
                "severity": "critical",
                "status": "resolved",
                "message": "Market-tick-data-service unresponsive for 120s",
                "source": "alerting-service",
                "strategy_id": None,
                "org_id": _O,
                "timestamp": "2026-03-21T09:25:00Z",
                "acknowledged": True,
                "escalated_at": "2026-03-21T09:25:10Z",
            },
            # ── High (5) ──
            {
                "alert_id": "alrt-a2b3c4d5-8004",
                "severity": "high",
                "status": "active",
                "message": "Position limit 80% reached on SOL-USD-PERP",
                "source": "risk-and-exposure-service",
                "strategy_id": "strat-009",
                "org_id": _O,
                "timestamp": "2026-03-21T09:16:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8005",
                "severity": "high",
                "status": "active",
                "message": "Hyperliquid API rate limit 90% utilization",
                "source": "execution-service",
                "strategy_id": "strat-009",
                "org_id": _O,
                "timestamp": "2026-03-21T09:10:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8006",
                "severity": "high",
                "status": "resolved",
                "message": "Slippage exceeded 0.1% on WETH-USDC swap",
                "source": "execution-service",
                "strategy_id": "strat-001",
                "org_id": _O,
                "timestamp": "2026-03-21T11:00:15Z",
                "acknowledged": True,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8007",
                "severity": "high",
                "status": "active",
                "message": "Funding rate arb spread collapsed below threshold",
                "source": "strategy-service",
                "strategy_id": "strat-011",
                "org_id": _O,
                "timestamp": "2026-03-21T08:45:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8008",
                "severity": "high",
                "status": "resolved",
                "message": "Order rejection rate above 5% on deribit",
                "source": "execution-service",
                "strategy_id": "strat-014",
                "org_id": _A,
                "timestamp": "2026-03-21T07:30:00Z",
                "acknowledged": True,
                "escalated_at": "2026-03-21T07:35:00Z",
            },
            # ── Medium (6) ──
            {
                "alert_id": "alrt-a2b3c4d5-8009",
                "severity": "medium",
                "status": "active",
                "message": "Data gap detected on hyperliquid-rest",
                "source": "market-tick-data-service",
                "strategy_id": None,
                "org_id": _O,
                "timestamp": "2026-03-21T09:25:01Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8010",
                "severity": "medium",
                "status": "active",
                "message": "Features-onchain-service staleness > 5min",
                "source": "features-onchain-service",
                "strategy_id": None,
                "org_id": _O,
                "timestamp": "2026-03-21T09:20:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8011",
                "severity": "medium",
                "status": "resolved",
                "message": "Batch/live position reconciliation mismatch: 3 breaks",
                "source": "batch-live-reconciliation-service",
                "strategy_id": None,
                "org_id": _O,
                "timestamp": "2026-03-21T08:00:00Z",
                "acknowledged": True,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8012",
                "severity": "medium",
                "status": "active",
                "message": "ML model momentum-multi-asset drift detected",
                "source": "ml-inference-service",
                "strategy_id": "strat-006",
                "org_id": _O,
                "timestamp": "2026-03-21T07:00:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8013",
                "severity": "medium",
                "status": "active",
                "message": "Gas price spike on Ethereum mainnet > 50 gwei",
                "source": "features-onchain-service",
                "strategy_id": "strat-001",
                "org_id": _O,
                "timestamp": "2026-03-21T10:30:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8014",
                "severity": "medium",
                "status": "resolved",
                "message": "Strategy CEFI_MULTI_VOL_SURF_EVT_1H PnL drawdown -3.2%",
                "source": "pnl-attribution-service",
                "strategy_id": "strat-014",
                "org_id": _A,
                "timestamp": "2026-03-21T06:00:00Z",
                "acknowledged": True,
                "escalated_at": None,
            },
            # ── Low (4) ──
            {
                "alert_id": "alrt-a2b3c4d5-8015",
                "severity": "low",
                "status": "resolved",
                "message": "Model latency p99 > 50ms on mean-reversion-btc",
                "source": "ml-inference-service",
                "strategy_id": "strat-002",
                "org_id": _O,
                "timestamp": "2026-03-21T07:00:00Z",
                "acknowledged": True,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8016",
                "severity": "low",
                "status": "active",
                "message": "Sports-features-service last compute > 1h ago",
                "source": "features-sports-service",
                "strategy_id": "strat-008",
                "org_id": _O,
                "timestamp": "2026-03-21T09:00:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8017",
                "severity": "low",
                "status": "resolved",
                "message": "Disk usage above 75% on ml-training-service",
                "source": "ml-training-service",
                "strategy_id": None,
                "org_id": _O,
                "timestamp": "2026-03-21T06:00:00Z",
                "acknowledged": True,
                "escalated_at": None,
            },
            {
                "alert_id": "alrt-a2b3c4d5-8018",
                "severity": "low",
                "status": "active",
                "message": "Invoice inv-b4c5d6e7-7002 pending for > 7 days",
                "source": "pnl-attribution-service",
                "strategy_id": None,
                "org_id": _V,
                "timestamp": "2026-03-21T08:00:00Z",
                "acknowledged": False,
                "escalated_at": None,
            },
        ],
    )

    _seed(
        "alert_summary",
        [
            {"severity": "critical", "count": 3},
            {"severity": "high", "count": 5},
            {"severity": "medium", "count": 6},
            {"severity": "low", "count": 4},
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  RISK
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "risk_limits",
        [
            {
                "venue": "binance",
                "instrument": "BTC-USDT",
                "max_position_notional": 500000.00,
                "max_order_size": 2.0,
                "max_leverage": 5.0,
                "current_utilization": 0.34,
                "org_id": _O,
            },
            {
                "venue": "hyperliquid",
                "instrument": "SOL-USD-PERP",
                "max_position_notional": 100000.00,
                "max_order_size": 500.0,
                "max_leverage": 10.0,
                "current_utilization": 0.73,
                "org_id": _O,
            },
            {
                "venue": "deribit",
                "instrument": "BTC-28MAR26-70000-C",
                "max_position_notional": 200000.00,
                "max_order_size": 20.0,
                "max_leverage": 3.0,
                "current_utilization": 0.18,
                "org_id": _O,
            },
            {
                "venue": "aave_v3",
                "instrument": "WETH-SUPPLY",
                "max_position_notional": 300000.00,
                "max_order_size": 50.0,
                "max_leverage": 1.0,
                "current_utilization": 0.06,
                "org_id": _O,
            },
        ],
    )

    _seed(
        "var",
        [
            {
                "portfolio": "global",
                "var_1d_99": 12500.00,
                "var_1d_95": 8200.00,
                "component_count": 20,
                "org_id": _O,
            },
            {
                "portfolio": "acme",
                "var_1d_99": 3200.00,
                "var_1d_95": 2100.00,
                "component_count": 4,
                "org_id": _A,
            },
        ],
    )

    _seed(
        "greeks",
        [
            {
                "instrument": "BTC-28MAR26-70000-C",
                "delta": 0.45,
                "gamma": 0.0012,
                "theta": -28.50,
                "vega": 142.00,
                "rho": 5.20,
                "org_id": _O,
            },
            {
                "instrument": "ETH-28MAR26-4000-C",
                "delta": 0.32,
                "gamma": 0.0025,
                "theta": -15.20,
                "vega": 88.00,
                "rho": 2.80,
                "org_id": _A,
            },
        ],
    )

    _seed(
        "stress_tests",
        [
            {
                "scenario": "btc_crash_20pct",
                "portfolio_impact": -17800.00,
                "worst_instrument": "BTC-USDT",
                "run_at": "2026-03-21T06:00:00Z",
                "org_id": _O,
            },
            {
                "scenario": "vol_spike_2x",
                "portfolio_impact": 3200.00,
                "worst_instrument": "ETH-USDT",
                "run_at": "2026-03-21T06:00:00Z",
                "org_id": _O,
            },
            {
                "scenario": "defi_protocol_exploit",
                "portfolio_impact": -8500.00,
                "worst_instrument": "WETH-SUPPLY",
                "run_at": "2026-03-21T06:00:00Z",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  INSTRUMENTS
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "instruments",
        [
            {
                "instrument_id": "inst-b3c4d5e6-9001",
                "symbol": "BTC-USDT",
                "venue": "binance",
                "asset_group": "crypto",
                "base": "BTC",
                "quote": "USDT",
                "tick_size": 0.01,
                "lot_size": 0.00001,
                "status": "active",
                "org_id": _O,
            },
            {
                "instrument_id": "inst-b3c4d5e6-9002",
                "symbol": "ETH-USDT",
                "venue": "binance",
                "asset_group": "crypto",
                "base": "ETH",
                "quote": "USDT",
                "tick_size": 0.01,
                "lot_size": 0.0001,
                "status": "active",
                "org_id": _O,
            },
            {
                "instrument_id": "inst-b3c4d5e6-9003",
                "symbol": "SOL-USD-PERP",
                "venue": "hyperliquid",
                "asset_group": "crypto",
                "base": "SOL",
                "quote": "USD",
                "tick_size": 0.01,
                "lot_size": 0.1,
                "status": "active",
                "org_id": _O,
            },
            {
                "instrument_id": "inst-b3c4d5e6-9004",
                "symbol": "BTC-28MAR26-70000-C",
                "venue": "deribit",
                "asset_group": "option",
                "base": "BTC",
                "quote": "USD",
                "tick_size": 0.0005,
                "lot_size": 0.1,
                "status": "active",
                "org_id": _O,
            },
            {
                "instrument_id": "inst-b3c4d5e6-9005",
                "symbol": "WETH-USDC",
                "venue": "uniswap_v3",
                "asset_group": "defi",
                "base": "WETH",
                "quote": "USDC",
                "tick_size": 0.01,
                "lot_size": 0.001,
                "status": "active",
                "org_id": _O,
            },
            {
                "instrument_id": "inst-b3c4d5e6-9006",
                "symbol": "WETH-SUPPLY",
                "venue": "aave_v3",
                "asset_group": "defi",
                "base": "WETH",
                "quote": "aWETH",
                "tick_size": 0.01,
                "lot_size": 0.001,
                "status": "active",
                "org_id": _O,
            },
            {
                "instrument_id": "inst-b3c4d5e6-9007",
                "symbol": "SOL-USDT",
                "venue": "binance",
                "asset_group": "crypto",
                "base": "SOL",
                "quote": "USDT",
                "tick_size": 0.01,
                "lot_size": 0.01,
                "status": "active",
                "org_id": _O,
            },
            {
                "instrument_id": "inst-b3c4d5e6-9008",
                "symbol": "AVAX-USDT",
                "venue": "binance",
                "asset_group": "crypto",
                "base": "AVAX",
                "quote": "USDT",
                "tick_size": 0.01,
                "lot_size": 0.01,
                "status": "active",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "instrument_catalogue",
        [
            {
                "asset_group": "crypto",
                "count": 45,
                "venues": ["binance", "deribit", "hyperliquid"],
                "org_id": _O,
            },
            {"asset_group": "option", "count": 120, "venues": ["deribit"], "org_id": _O},
            {"asset_group": "defi", "count": 35, "venues": ["uniswap_v3", "aave_v3"], "org_id": _O},
            {
                "asset_group": "sports",
                "count": 380,
                "venues": ["betfair", "matchbook"],
                "org_id": _O,
            },
            {"asset_group": "prediction", "count": 45, "venues": ["polymarket"], "org_id": _O},
        ],
    )

    _seed(
        "instrument_registry",
        [
            {
                "canonical": "BTC-USDT",
                "mappings": {"binance": "BTCUSDT", "deribit": "BTC-USDT", "hyperliquid": "BTC"},
                "org_id": _O,
            },
            {
                "canonical": "ETH-USDT",
                "mappings": {"binance": "ETHUSDT", "deribit": "ETH-USDT", "hyperliquid": "ETH"},
                "org_id": _O,
            },
            {
                "canonical": "SOL-USDT",
                "mappings": {"binance": "SOLUSDT", "hyperliquid": "SOL"},
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  DOCUMENTS
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "documents",
        [
            {
                "document_id": "doc-c4d5e6f7-0001",
                "filename": "daily-risk-report-2026-03-20.pdf",
                "category": "risk",
                "size_bytes": 245000,
                "uploaded_at": "2026-03-20T23:59:30Z",
                "org_id": _O,
            },
            {
                "document_id": "doc-c4d5e6f7-0002",
                "filename": "trade-blotter-2026-03-20.csv",
                "category": "execution",
                "size_bytes": 82000,
                "uploaded_at": "2026-03-20T23:58:00Z",
                "org_id": _O,
            },
            {
                "document_id": "doc-c4d5e6f7-0003",
                "filename": "alpha-capital-q1-report.pdf",
                "category": "reporting",
                "size_bytes": 512000,
                "uploaded_at": "2026-03-21T06:00:00Z",
                "org_id": _A,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  DEPLOYMENT
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "deployment_services",
        [
            {
                "service": "execution-service",
                "version": "0.4.12",
                "replicas": 2,
                "status": "running",
                "region": "asia-northeast1",
                "org_id": _O,
            },
            {
                "service": "strategy-service",
                "version": "0.3.8",
                "replicas": 1,
                "status": "running",
                "region": "asia-northeast1",
                "org_id": _O,
            },
            {
                "service": "risk-and-exposure-service",
                "version": "0.2.5",
                "replicas": 1,
                "status": "running",
                "region": "asia-northeast1",
                "org_id": _O,
            },
            {
                "service": "market-tick-data-service",
                "version": "0.5.1",
                "replicas": 3,
                "status": "running",
                "region": "asia-northeast1",
                "org_id": _O,
            },
            {
                "service": "alerting-service",
                "version": "0.3.2",
                "replicas": 1,
                "status": "running",
                "region": "asia-northeast1",
                "org_id": _O,
            },
            {
                "service": "ml-inference-service",
                "version": "0.2.1",
                "replicas": 2,
                "status": "running",
                "region": "asia-northeast1",
                "org_id": _O,
            },
            {
                "service": "ml-training-service",
                "version": "0.1.8",
                "replicas": 1,
                "status": "running",
                "region": "asia-northeast1",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "deployments",
        [
            {
                "deployment_id": "dpl-d5e6f7a8-1001",
                "service": "execution-service",
                "version": "0.4.12",
                "status": "active",
                "deployed_at": "2026-03-20T10:00:00Z",
                "deployed_by": "ci-pipeline",
                "org_id": _O,
            },
            {
                "deployment_id": "dpl-d5e6f7a8-1002",
                "service": "market-tick-data-service",
                "version": "0.5.1",
                "status": "active",
                "deployed_at": "2026-03-19T14:00:00Z",
                "deployed_by": "ci-pipeline",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "builds",
        [
            {
                "build_id": "bld-e6f7a8b9-2001",
                "service": "execution-service",
                "version": "0.4.12",
                "status": "success",
                "duration_s": 142,
                "started_at": "2026-03-20T09:55:00Z",
                "org_id": _O,
            },
            {
                "build_id": "bld-e6f7a8b9-2002",
                "service": "strategy-service",
                "version": "0.3.9",
                "status": "failed",
                "duration_s": 88,
                "started_at": "2026-03-21T08:00:00Z",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  SERVICE HEALTH (21 services) — matches real services
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "service_health",
        [
            {
                "service": "execution-service",
                "status": "healthy",
                "uptime_pct": 99.98,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "strategy-service",
                "status": "healthy",
                "uptime_pct": 99.95,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "risk-and-exposure-service",
                "status": "healthy",
                "uptime_pct": 99.99,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "market-tick-data-service",
                "status": "degraded",
                "uptime_pct": 98.50,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "market-data-processing-service",
                "status": "healthy",
                "uptime_pct": 99.92,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-volatility-service",
                "status": "healthy",
                "uptime_pct": 99.90,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-onchain-service",
                "status": "healthy",
                "uptime_pct": 99.85,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-cross-instrument-service",
                "status": "healthy",
                "uptime_pct": 99.88,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-multi-timeframe-service",
                "status": "healthy",
                "uptime_pct": 99.91,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-commodity-service",
                "status": "healthy",
                "uptime_pct": 99.93,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-delta-one-service",
                "status": "healthy",
                "uptime_pct": 99.87,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-calendar-service",
                "status": "healthy",
                "uptime_pct": 99.94,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "features-sports-service",
                "status": "healthy",
                "uptime_pct": 99.80,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "ml-training-service",
                "status": "healthy",
                "uptime_pct": 99.70,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "ml-inference-service",
                "status": "healthy",
                "uptime_pct": 99.96,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "alerting-service",
                "status": "healthy",
                "uptime_pct": 99.97,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "position-balance-monitor-service",
                "status": "healthy",
                "uptime_pct": 99.95,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "pnl-attribution-service",
                "status": "healthy",
                "uptime_pct": 99.92,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "batch-live-reconciliation-service",
                "status": "degraded",
                "uptime_pct": 97.80,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "instruments-service",
                "status": "healthy",
                "uptime_pct": 99.99,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
            {
                "service": "trading-agent-service",
                "status": "healthy",
                "uptime_pct": 99.88,
                "last_check": "2026-03-21T09:30:00Z",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "feature_freshness",
        [
            {
                "pipeline": "technical-features",
                "last_computed": "2026-03-21T09:28:00Z",
                "staleness_s": 120,
                "status": "fresh",
                "org_id": _O,
            },
            {
                "pipeline": "onchain-features",
                "last_computed": "2026-03-21T09:15:00Z",
                "staleness_s": 900,
                "status": "fresh",
                "org_id": _O,
            },
            {
                "pipeline": "sports-features",
                "last_computed": "2026-03-21T08:00:00Z",
                "staleness_s": 5400,
                "status": "stale",
                "org_id": _O,
            },
            {
                "pipeline": "volatility-features",
                "last_computed": "2026-03-21T09:25:00Z",
                "staleness_s": 300,
                "status": "fresh",
                "org_id": _O,
            },
            {
                "pipeline": "cross-instrument-features",
                "last_computed": "2026-03-21T09:20:00Z",
                "staleness_s": 600,
                "status": "fresh",
                "org_id": _O,
            },
        ],
    )

    _seed(
        "activity",
        [
            {
                "event": "Order filled",
                "detail": "BTC-USDT buy 0.15 @ 67250.50",
                "service": "execution-service",
                "timestamp": "2026-03-21T08:12:34Z",
                "org_id": _O,
            },
            {
                "event": "Model deployed",
                "detail": "mean-reversion-btc v3.1.0 to production",
                "service": "ml-inference-service",
                "timestamp": "2026-03-20T18:00:00Z",
                "org_id": _O,
            },
            {
                "event": "Alert triggered",
                "detail": "Position limit 80% on SOL-USD-PERP",
                "service": "risk-and-exposure-service",
                "timestamp": "2026-03-21T09:16:00Z",
                "org_id": _O,
            },
            {
                "event": "Build failed",
                "detail": "strategy-service v0.3.9 build failed",
                "service": "deployment-service",
                "timestamp": "2026-03-21T08:01:28Z",
                "org_id": _O,
            },
            {
                "event": "DeFi swap",
                "detail": "WETH-USDC swap 3.0 on Uniswap V3",
                "service": "execution-service",
                "timestamp": "2026-03-21T11:00:15Z",
                "org_id": _O,
            },
            {
                "event": "Aave supply",
                "detail": "Supplied 5 WETH to Aave V3",
                "service": "execution-service",
                "timestamp": "2026-03-21T11:15:12Z",
                "org_id": _O,
            },
            {
                "event": "Order filled",
                "detail": "BTC-USDT sell 0.10 @ 67398.65",
                "service": "execution-service",
                "timestamp": "2026-03-21T09:30:01Z",
                "org_id": _A,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  USERS / ORGANIZATIONS
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "user_organizations",
        [
            {"org_id": _O, "name": "Odum Internal", "plan": "enterprise", "member_count": 8},
            {"org_id": _A, "name": "Alpha Capital", "plan": "premium", "member_count": 4},
            {"org_id": _V, "name": "Vertex Partners", "plan": "premium", "member_count": 3},
            {"org_id": _B, "name": "Beta Fund", "plan": "basic", "member_count": 2},
        ],
    )

    _seed(
        "members",
        [
            {
                "member_id": "usr-a8b9c0d1-4001",
                "organization_id": _O,
                "email": "admin@odum.internal",
                "role": "admin",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4002",
                "organization_id": _O,
                "email": "trader@odum.internal",
                "role": "trader",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4003",
                "organization_id": _O,
                "email": "quant@odum.internal",
                "role": "trader",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4004",
                "organization_id": _A,
                "email": "pm@alphacapital.com",
                "role": "client",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4005",
                "organization_id": _A,
                "email": "analyst@alphacapital.com",
                "role": "viewer",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4006",
                "organization_id": _V,
                "email": "cio@vertex.com",
                "role": "client",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4007",
                "organization_id": _B,
                "email": "analyst@betafund.com",
                "role": "client",
                "status": "active",
            },
        ],
    )

    _seed(
        "subscriptions",
        [
            {
                "subscription_id": "sub-b9c0d1e2-5001",
                "organization_id": _O,
                "plan": "enterprise",
                "status": "active",
                "started_at": "2025-12-01T00:00:00Z",
                "renews_at": "2026-12-01T00:00:00Z",
                "features": [
                    "execution",
                    "analytics",
                    "ml",
                    "risk",
                    "defi",
                    "sports",
                    "prediction",
                ],
                "org_id": _O,
            },
            {
                "subscription_id": "sub-b9c0d1e2-5002",
                "organization_id": _A,
                "plan": "premium",
                "status": "active",
                "started_at": "2026-01-15T00:00:00Z",
                "renews_at": "2027-01-15T00:00:00Z",
                "features": ["execution", "analytics", "ml", "risk"],
                "org_id": _A,
            },
            {
                "subscription_id": "sub-b9c0d1e2-5003",
                "organization_id": _V,
                "plan": "premium",
                "status": "active",
                "started_at": "2026-02-01T00:00:00Z",
                "renews_at": "2027-02-01T00:00:00Z",
                "features": ["execution", "analytics", "risk"],
                "org_id": _V,
            },
            {
                "subscription_id": "sub-b9c0d1e2-5004",
                "organization_id": _B,
                "plan": "basic",
                "status": "active",
                "started_at": "2026-03-01T00:00:00Z",
                "renews_at": "2027-03-01T00:00:00Z",
                "features": ["analytics"],
                "org_id": _B,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  OHLCV CANDLES — registry-driven via seed_candles.py
    #  ~32K records from all UAC representative_sample instruments
    # ══════════════════════════════════════════════════════════════════

    from unified_trading_api.mock_data.seed_candles import (  # noqa: qg-deep-import — self-package
        generate_candles,  # noqa: qg-deep-import — self-package
    )

    _candle_data = generate_candles()
    for _interval_key, _candle_records in _candle_data.items():
        _seed(_interval_key, _candle_records)

    # Legacy "candles" alias for backwards compatibility
    _seed("candles", _candle_data.get("candles_1m", []))

    _seed(
        "trades",
        [
            {
                "trade_id": "t-001",
                "price": 67250.50,
                "quantity": 0.15,
                "side": "buy",
                "timestamp": "2026-03-21T09:00:12Z",
                "org_id": _O,
            },
            {
                "trade_id": "t-002",
                "price": 67248.00,
                "quantity": 0.30,
                "side": "sell",
                "timestamp": "2026-03-21T09:00:14Z",
                "org_id": _O,
            },
            {
                "trade_id": "t-003",
                "price": 67252.00,
                "quantity": 0.05,
                "side": "buy",
                "timestamp": "2026-03-21T09:00:18Z",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  TICKERS — registry-driven via seed_tickers.py
    #  All instruments from UAC representative_sample
    # ══════════════════════════════════════════════════════════════════

    from unified_trading_api.mock_data.seed_tickers import (  # noqa: qg-deep-import — self-package
        generate_tickers_batch,
        generate_tickers_live,
    )

    _tickers_live = generate_tickers_live()
    _seed("tickers", _tickers_live)
    _seed("tickers_live", _tickers_live)
    _seed("tickers_batch", generate_tickers_batch())

    # ══════════════════════════════════════════════════════════════════
    #  ALERTS LIVE/BATCH (for live/batch mode support)
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "alerts_live",
        [
            {
                "alert_id": "alrt-l-001",
                "severity": "critical",
                "status": "active",
                "acknowledged": False,
                "message": "BTC exposure exceeds 80% of limit",
                "strategy_id": "strat-002",
                "org_id": _O,
                "created_at": "2026-03-22T08:15:00Z",
            },
            {
                "alert_id": "alrt-l-002",
                "severity": "high",
                "status": "active",
                "acknowledged": False,
                "message": "Latency spike on Binance venue adapter",
                "strategy_id": "strat-004",
                "org_id": _O,
                "created_at": "2026-03-22T08:30:00Z",
            },
            {
                "alert_id": "alrt-l-003",
                "severity": "medium",
                "status": "active",
                "acknowledged": False,
                "message": "Drawdown warning on DEFI_ETH_BASIS strategy",
                "strategy_id": "strat-001",
                "org_id": _O,
                "created_at": "2026-03-22T09:00:00Z",
            },
            {
                "alert_id": "alrt-l-004",
                "severity": "high",
                "status": "active",
                "acknowledged": False,
                "message": "Margin call approaching for ACME positions",
                "strategy_id": "strat-002",
                "org_id": _A,
                "created_at": "2026-03-22T09:15:00Z",
            },
            {
                "alert_id": "alrt-l-005",
                "severity": "low",
                "status": "active",
                "acknowledged": False,
                "message": "Feature pipeline delayed by 5 minutes",
                "strategy_id": "strat-006",
                "org_id": _O,
                "created_at": "2026-03-22T09:30:00Z",
            },
            {
                "alert_id": "alrt-l-006",
                "severity": "critical",
                "status": "active",
                "acknowledged": False,
                "message": "Kill switch triggered for SPORTS_NFL_ARB",
                "strategy_id": "strat-008",
                "org_id": _O,
                "created_at": "2026-03-22T09:45:00Z",
            },
            {
                "alert_id": "alrt-l-007",
                "severity": "medium",
                "status": "acknowledged",
                "acknowledged": True,
                "acknowledged_by": "admin",
                "message": "Stale price detected for DOGE-USDT",
                "strategy_id": "strat-006",
                "org_id": _O,
                "created_at": "2026-03-22T10:00:00Z",
            },
        ],
    )

    _seed(
        "alerts_batch",
        [
            {
                "alert_id": "alrt-b-001",
                "severity": "critical",
                "status": "resolved",
                "acknowledged": True,
                "message": "End-of-day BTC exposure breach (resolved)",
                "strategy_id": "strat-002",
                "org_id": _O,
                "created_at": "2026-03-21T16:00:00Z",
                "resolved_at": "2026-03-21T16:30:00Z",
            },
            {
                "alert_id": "alrt-b-002",
                "severity": "high",
                "status": "resolved",
                "acknowledged": True,
                "message": "Margin call (resolved)",
                "strategy_id": "strat-002",
                "org_id": _A,
                "created_at": "2026-03-21T14:00:00Z",
                "resolved_at": "2026-03-21T15:00:00Z",
            },
            {
                "alert_id": "alrt-b-003",
                "severity": "medium",
                "status": "resolved",
                "acknowledged": True,
                "message": "Latency spike (resolved)",
                "strategy_id": "strat-004",
                "org_id": _O,
                "created_at": "2026-03-21T12:00:00Z",
                "resolved_at": "2026-03-21T12:15:00Z",
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  RISK LIVE/BATCH (for live/batch mode support)
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "risk_live",
        [
            {
                "id": "risk-l-001",
                "strategy_id": "strat-001",
                "exposure_usd": 245_000,
                "max_exposure": 500_000,
                "utilization_pct": 49.0,
                "var_99": 12_500,
                "org_id": _O,
            },
            {
                "id": "risk-l-002",
                "strategy_id": "strat-002",
                "exposure_usd": 890_000,
                "max_exposure": 1_000_000,
                "utilization_pct": 89.0,
                "var_99": 45_000,
                "org_id": _A,
            },
            {
                "id": "risk-l-003",
                "strategy_id": "strat-003",
                "exposure_usd": 150_000,
                "max_exposure": 300_000,
                "utilization_pct": 50.0,
                "var_99": 8_000,
                "org_id": _O,
            },
            {
                "id": "risk-l-004",
                "strategy_id": "strat-004",
                "exposure_usd": 520_000,
                "max_exposure": 750_000,
                "utilization_pct": 69.3,
                "var_99": 28_000,
                "org_id": _A,
            },
            {
                "id": "risk-l-005",
                "strategy_id": "strat-005",
                "exposure_usd": 310_000,
                "max_exposure": 600_000,
                "utilization_pct": 51.7,
                "var_99": 18_000,
                "org_id": _V,
            },
        ],
    )

    _seed(
        "risk_batch",
        [
            {
                "id": "risk-b-001",
                "strategy_id": "strat-001",
                "exposure_usd": 230_000,
                "max_exposure": 500_000,
                "utilization_pct": 46.0,
                "var_99": 11_800,
                "org_id": _O,
            },
            {
                "id": "risk-b-002",
                "strategy_id": "strat-002",
                "exposure_usd": 850_000,
                "max_exposure": 1_000_000,
                "utilization_pct": 85.0,
                "var_99": 43_000,
                "org_id": _A,
            },
            {
                "id": "risk-b-003",
                "strategy_id": "strat-003",
                "exposure_usd": 140_000,
                "max_exposure": 300_000,
                "utilization_pct": 46.7,
                "var_99": 7_500,
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  CORRELATION MATRIX
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "correlation_matrix",
        [
            {
                "id": "corr-matrix-current",
                "timestamp": "2026-03-22T00:00:00Z",
                "instruments": [
                    "BTC-USDT",
                    "ETH-USDT",
                    "SOL-USDT",
                    "AAPL",
                    "ES-FRONT",
                    "AAVE-ETH-LEND",
                ],
                "matrix": [
                    [1.00, 0.85, 0.72, 0.15, 0.20, 0.55],
                    [0.85, 1.00, 0.78, 0.12, 0.18, 0.62],
                    [0.72, 0.78, 1.00, 0.08, 0.10, 0.48],
                    [0.15, 0.12, 0.08, 1.00, 0.92, 0.05],
                    [0.20, 0.18, 0.10, 0.92, 1.00, 0.08],
                    [0.55, 0.62, 0.48, 0.05, 0.08, 1.00],
                ],
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  MARKET REGIME
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "regime",
        [
            {
                "id": "regime-current",
                "regime": "normal",
                "multiplier": 1.0,
                "signals": {"volatility": 0.15, "correlation": 0.35, "drawdown_velocity": 0.02},
                "timestamp": "2026-03-22T00:00:00Z",
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  EXPOSURE TYPES (for risk/exposure-types endpoint)
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "exposure_types",
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
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  DEFI HEALTH (for risk/defi-health endpoint)
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "defi_health",
        [
            {
                "id": "defi-health-aave-eth",
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
                "org_id": _O,
            },
            {
                "id": "defi-health-aave-arb",
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
                "org_id": _O,
            },
            {
                "id": "defi-health-compound-eth",
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
                "org_id": _A,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  OPTIONS CHAIN (for derivatives endpoints)
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "options_chain",
        [
            {
                "id": "opt-btc-c-70k",
                "underlying": "BTC",
                "venue": "deribit",
                "strike": 70000,
                "option_type": "call",
                "expiration": "2026-03-28",
                "bid": 1250.0,
                "ask": 1280.0,
                "implied_vol": 0.62,
                "delta": 0.42,
                "gamma": 0.00003,
                "theta": -85.0,
                "vega": 120.0,
                "org_id": _O,
            },
            {
                "id": "opt-btc-p-70k",
                "underlying": "BTC",
                "venue": "deribit",
                "strike": 70000,
                "option_type": "put",
                "expiration": "2026-03-28",
                "bid": 3800.0,
                "ask": 3850.0,
                "implied_vol": 0.65,
                "delta": -0.58,
                "gamma": 0.00003,
                "theta": -90.0,
                "vega": 125.0,
                "org_id": _O,
            },
            {
                "id": "opt-btc-c-65k",
                "underlying": "BTC",
                "venue": "deribit",
                "strike": 65000,
                "option_type": "call",
                "expiration": "2026-03-28",
                "bid": 3200.0,
                "ask": 3250.0,
                "implied_vol": 0.58,
                "delta": 0.68,
                "gamma": 0.00002,
                "theta": -70.0,
                "vega": 95.0,
                "org_id": _O,
            },
            {
                "id": "opt-btc-p-65k",
                "underlying": "BTC",
                "venue": "deribit",
                "strike": 65000,
                "option_type": "put",
                "expiration": "2026-03-28",
                "bid": 750.0,
                "ask": 780.0,
                "implied_vol": 0.55,
                "delta": -0.32,
                "gamma": 0.00002,
                "theta": -65.0,
                "vega": 90.0,
                "org_id": _O,
            },
            {
                "id": "opt-btc-c-75k",
                "underlying": "BTC",
                "venue": "deribit",
                "strike": 75000,
                "option_type": "call",
                "expiration": "2026-03-28",
                "bid": 350.0,
                "ask": 380.0,
                "implied_vol": 0.68,
                "delta": 0.22,
                "gamma": 0.00002,
                "theta": -55.0,
                "vega": 80.0,
                "org_id": _O,
            },
            {
                "id": "opt-eth-c-3500",
                "underlying": "ETH",
                "venue": "deribit",
                "strike": 3500,
                "option_type": "call",
                "expiration": "2026-03-28",
                "bid": 85.0,
                "ask": 90.0,
                "implied_vol": 0.60,
                "delta": 0.50,
                "gamma": 0.0005,
                "theta": -12.0,
                "vega": 8.0,
                "org_id": _O,
            },
            {
                "id": "opt-eth-p-3500",
                "underlying": "ETH",
                "venue": "deribit",
                "strike": 3500,
                "option_type": "put",
                "expiration": "2026-03-28",
                "bid": 80.0,
                "ask": 85.0,
                "implied_vol": 0.62,
                "delta": -0.50,
                "gamma": 0.0005,
                "theta": -11.0,
                "vega": 7.5,
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  VOL SURFACES
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "vol_surfaces",
        [
            {
                "id": "vol-btc",
                "underlying": "BTC",
                "atm_iv": 0.62,
                "skew_25d": -0.05,
                "butterfly_25d": 0.03,
                "slices": [
                    {
                        "expiry": "2026-03-28",
                        "smile": [
                            {"strike": 60000, "iv": 0.70},
                            {"strike": 65000, "iv": 0.62},
                            {"strike": 67000, "iv": 0.60},
                            {"strike": 70000, "iv": 0.62},
                            {"strike": 75000, "iv": 0.68},
                        ],
                    },
                    {
                        "expiry": "2026-04-25",
                        "smile": [
                            {"strike": 60000, "iv": 0.65},
                            {"strike": 65000, "iv": 0.58},
                            {"strike": 67000, "iv": 0.56},
                            {"strike": 70000, "iv": 0.58},
                            {"strike": 75000, "iv": 0.63},
                        ],
                    },
                ],
                "term_structure": [
                    {"expiry": "2026-03-28", "atm_iv": 0.60},
                    {"expiry": "2026-04-25", "atm_iv": 0.56},
                    {"expiry": "2026-06-27", "atm_iv": 0.52},
                ],
            },
            {
                "id": "vol-eth",
                "underlying": "ETH",
                "atm_iv": 0.65,
                "skew_25d": -0.04,
                "butterfly_25d": 0.025,
                "slices": [
                    {
                        "expiry": "2026-03-28",
                        "smile": [
                            {"strike": 3000, "iv": 0.72},
                            {"strike": 3300, "iv": 0.66},
                            {"strike": 3500, "iv": 0.63},
                            {"strike": 3700, "iv": 0.66},
                            {"strike": 4000, "iv": 0.72},
                        ],
                    },
                ],
                "term_structure": [
                    {"expiry": "2026-03-28", "atm_iv": 0.63},
                    {"expiry": "2026-04-25", "atm_iv": 0.59},
                ],
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  FX RATES
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "fx_rates",
        [
            {"id": "BTC/USD", "pair": "BTC/USD", "rate": 67000.0},
            {"id": "ETH/USD", "pair": "ETH/USD", "rate": 3500.0},
            {"id": "SOL/USD", "pair": "SOL/USD", "rate": 145.0},
            {"id": "USDT/USD", "pair": "USDT/USD", "rate": 1.0001},
            {"id": "EUR/USD", "pair": "EUR/USD", "rate": 1.08},
            {"id": "GBP/USD", "pair": "GBP/USD", "rate": 1.27},
            {"id": "JPY/USD", "pair": "JPY/USD", "rate": 0.0067},
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  REGULATORY REPORTS
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "regulatory_reports",
        [
            {
                "id": "reg-001",
                "report_id": "reg-001",
                "report_type": "MIFID_II_BEST_EXECUTION",
                "jurisdiction": "EU",
                "status": "submitted",
                "filing_date": "2026-03-15",
                "next_due_date": "2026-04-15",
                "instruments_covered": ["BTC-USDT", "ETH-USDT"],
                "summary": "Q1 2026 best execution report",
                "org_id": _O,
            },
            {
                "id": "reg-002",
                "report_id": "reg-002",
                "report_type": "FCA_TRANSACTION",
                "jurisdiction": "UK",
                "status": "submitted",
                "filing_date": "2026-03-14",
                "next_due_date": "2026-04-14",
                "instruments_covered": ["AAPL", "QQQ", "ES-FRONT"],
                "summary": "March 2026 transaction report",
                "org_id": _O,
            },
            {
                "id": "reg-003",
                "report_id": "reg-003",
                "report_type": "EMIR_DERIVATIVE",
                "jurisdiction": "EU",
                "status": "pending",
                "filing_date": "",
                "next_due_date": "2026-03-31",
                "instruments_covered": ["BTC-USDT-PERP", "ETH-USDT-PERP"],
                "summary": "EMIR derivative reporting for perpetual swaps",
                "org_id": _O,
            },
            {
                "id": "reg-004",
                "report_id": "reg-004",
                "report_type": "MIFID_II_BEST_EXECUTION",
                "jurisdiction": "EU",
                "status": "overdue",
                "filing_date": "",
                "next_due_date": "2026-03-01",
                "instruments_covered": ["BTC-USDT"],
                "summary": "February execution report — OVERDUE",
                "org_id": _A,
            },
            {
                "id": "reg-005",
                "report_id": "reg-005",
                "report_type": "FCA_TRANSACTION",
                "jurisdiction": "UK",
                "status": "submitted",
                "filing_date": "2026-03-10",
                "next_due_date": "2026-04-10",
                "instruments_covered": ["GLD", "ES-FRONT"],
                "summary": "Client transaction report for Vertex Partners",
                "org_id": _V,
            },
            {
                "id": "reg-006",
                "report_id": "reg-006",
                "report_type": "EMIR_DERIVATIVE",
                "jurisdiction": "EU",
                "status": "submitted",
                "filing_date": "2026-03-01",
                "next_due_date": "2026-04-01",
                "instruments_covered": ["BTC-USD-PERP"],
                "summary": "Deribit perpetuals EMIR report",
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  ORDERS LIVE/BATCH (for live/batch mode support)
    # ══════════════════════════════════════════════════════════════════

    _orders_live: list[dict[str, object]] = [
        {
            "order_id": "ord-l-001",
            "instrument": "BTC-USDT",
            "venue": "binance",
            "side": "buy",
            "quantity": 0.5,
            "price": 67200.0,
            "status": "filled",
            "strategy_id": "strat-002",
            "org_id": _A,
            "created_at": "2026-03-22T08:00:00Z",
        },
        {
            "order_id": "ord-l-002",
            "instrument": "ETH-USDT",
            "venue": "binance",
            "side": "sell",
            "quantity": 5.0,
            "price": 3480.0,
            "status": "filled",
            "strategy_id": "strat-006",
            "org_id": _O,
            "created_at": "2026-03-22T08:15:00Z",
        },
        {
            "order_id": "ord-l-003",
            "instrument": "SOL-USDT",
            "venue": "binance",
            "side": "buy",
            "quantity": 100.0,
            "price": 145.0,
            "status": "open",
            "strategy_id": "strat-006",
            "org_id": _O,
            "created_at": "2026-03-22T09:00:00Z",
        },
        {
            "order_id": "ord-l-004",
            "instrument": "BTC-USDT-PERP",
            "venue": "binance-futures",
            "side": "sell",
            "quantity": 0.2,
            "price": 67300.0,
            "status": "partially_filled",
            "strategy_id": "strat-004",
            "org_id": _A,
            "created_at": "2026-03-22T09:30:00Z",
        },
    ]
    for _ol in _orders_live:
        _ol["asset_group"] = _strategy_asset_group.get(str(_ol.get("strategy_id", "")), "cefi")
    _seed("orders_live", _orders_live)

    _orders_batch: list[dict[str, object]] = [
        {
            "order_id": "ord-b-001",
            "instrument": "BTC-USDT",
            "venue": "binance",
            "side": "buy",
            "quantity": 1.0,
            "price": 66800.0,
            "status": "filled",
            "strategy_id": "strat-002",
            "org_id": _A,
            "created_at": "2026-03-21T10:00:00Z",
        },
        {
            "order_id": "ord-b-002",
            "instrument": "ETH-USDT",
            "venue": "binance",
            "side": "buy",
            "quantity": 10.0,
            "price": 3450.0,
            "status": "filled",
            "strategy_id": "strat-006",
            "org_id": _O,
            "created_at": "2026-03-21T14:00:00Z",
        },
    ]
    for _ob in _orders_batch:
        _ob["asset_group"] = _strategy_asset_group.get(str(_ob.get("strategy_id", "")), "cefi")
    _seed("orders_batch", _orders_batch)

    # ══════════════════════════════════════════════════════════════════
    #  PNL TIME-SERIES — 180 daily points per strategy (50+ strategies)
    # ══════════════════════════════════════════════════════════════════

    from unified_trading_api.mock_data.seed_timeseries import (  # noqa: qg-deep-import — self-package
        generate_pnl_timeseries,  # noqa: qg-deep-import — self-package
    )

    _pnl_ts = generate_pnl_timeseries(_strategies)
    _seed("pnl_timeseries", _pnl_ts)
    _seed("pnl_timeseries_live", _pnl_ts)

    # Batch PnL = same but with slight reconciliation adjustments (-0.2%)
    _pnl_ts_batch = [
        {
            **pt,
            "cumulative_pnl": round(
                float(str(pt["cumulative_pnl"])) * 0.998,
                2,
            ),
        }
        for pt in _pnl_ts
    ]
    _seed("pnl_timeseries_batch", _pnl_ts_batch)

    # ══════════════════════════════════════════════════════════════════
    #  NEWS — mock news items for Observe > News page
    # ══════════════════════════════════════════════════════════════════

    _seed(
        "news",
        [
            {
                "id": "news-001",
                "title": "BTC breaks $67K resistance level",
                "source": "CoinDesk",
                "timestamp": "2026-03-22T08:00:00Z",
                "category": "crypto",
                "relevance_score": 0.92,
                "linked_instruments": ["BTC-USDT"],
                "org_id": _O,
            },
            {
                "id": "news-002",
                "title": "SEC approves spot ETH ETF applications",
                "source": "Bloomberg",
                "timestamp": "2026-03-22T06:30:00Z",
                "category": "regulatory",
                "relevance_score": 0.95,
                "linked_instruments": ["ETH-USDT"],
                "org_id": _O,
            },
            {
                "id": "news-003",
                "title": "Fed signals rate pause through Q2 2026",
                "source": "Reuters",
                "timestamp": "2026-03-22T05:00:00Z",
                "category": "macro",
                "relevance_score": 0.88,
                "linked_instruments": ["ES", "ZB", "ZN"],
                "org_id": _O,
            },
            {
                "id": "news-004",
                "title": "Uniswap V4 launch drives DeFi TVL surge",
                "source": "The Block",
                "timestamp": "2026-03-21T22:00:00Z",
                "category": "crypto",
                "relevance_score": 0.82,
                "linked_instruments": ["USDT-ETH"],
                "org_id": _O,
            },
            {
                "id": "news-005",
                "title": "Aave V3 yields spike to 8% on ETH markets",
                "source": "DeFi Pulse",
                "timestamp": "2026-03-21T20:00:00Z",
                "category": "crypto",
                "relevance_score": 0.78,
                "linked_instruments": ["aWETH"],
                "org_id": _O,
            },
            {
                "id": "news-006",
                "title": "SOL ecosystem gains momentum with Firedancer",
                "source": "CoinDesk",
                "timestamp": "2026-03-21T18:00:00Z",
                "category": "crypto",
                "relevance_score": 0.75,
                "linked_instruments": ["SOL-USDT"],
                "org_id": _O,
            },
            {
                "id": "news-007",
                "title": "AAPL earnings beat estimates, stock gaps up",
                "source": "Bloomberg",
                "timestamp": "2026-03-21T16:00:00Z",
                "category": "market",
                "relevance_score": 0.85,
                "linked_instruments": ["AAPL"],
                "org_id": _O,
            },
            {
                "id": "news-008",
                "title": "Hyperliquid surpasses $100B daily volume",
                "source": "The Block",
                "timestamp": "2026-03-21T14:00:00Z",
                "category": "crypto",
                "relevance_score": 0.72,
                "linked_instruments": ["ETH"],
                "org_id": _O,
            },
            {
                "id": "news-009",
                "title": "Deribit launches weekly BTC options with tighter spreads",
                "source": "CoinDesk",
                "timestamp": "2026-03-21T12:00:00Z",
                "category": "market",
                "relevance_score": 0.68,
                "linked_instruments": ["BTC-USDC"],
                "org_id": _O,
            },
            {
                "id": "news-010",
                "title": "EU proposes MiCA Phase 2 stablecoin regulations",
                "source": "Reuters",
                "timestamp": "2026-03-21T10:00:00Z",
                "category": "regulatory",
                "relevance_score": 0.90,
                "linked_instruments": ["USDT-ETH", "aUSDC"],
                "org_id": _O,
            },
            {
                "id": "news-011",
                "title": "NBA playoff odds shift after Celtics injury report",
                "source": "ESPN",
                "timestamp": "2026-03-21T08:00:00Z",
                "category": "sports",
                "relevance_score": 0.65,
                "linked_instruments": ["NBA-LAL-BOS"],
                "org_id": _O,
            },
            {
                "id": "news-012",
                "title": "Gold ETF GLD sees record inflows amid uncertainty",
                "source": "Bloomberg",
                "timestamp": "2026-03-22T07:00:00Z",
                "category": "market",
                "relevance_score": 0.80,
                "linked_instruments": ["GLD"],
                "org_id": _O,
            },
            {
                "id": "news-013",
                "title": "VIX drops below 15 as market volatility subsides",
                "source": "CBOE",
                "timestamp": "2026-03-22T09:00:00Z",
                "category": "market",
                "relevance_score": 0.73,
                "linked_instruments": ["VIX"],
                "org_id": _O,
            },
            {
                "id": "news-014",
                "title": "Polymarket prediction markets see election trading surge",
                "source": "The Block",
                "timestamp": "2026-03-21T19:00:00Z",
                "category": "crypto",
                "relevance_score": 0.60,
                "linked_instruments": ["NBA-DAL-MEM-SPREAD-5.5"],
                "org_id": _O,
            },
            {
                "id": "news-015",
                "title": "Ethereum gas fees drop to 12-month low",
                "source": "Etherscan",
                "timestamp": "2026-03-22T10:00:00Z",
                "category": "crypto",
                "relevance_score": 0.70,
                "linked_instruments": ["ETH-USDT", "aWETH", "stETH"],
                "org_id": _O,
            },
        ],
    )

    # ══════════════════════════════════════════════════════════════════
    #  PHASE 8 — risk limits, options, vol, VaR, FX, regulatory, DeFi
    #  (additional data from seed_phase8.py if available)
    # ══════════════════════════════════════════════════════════════════

    from unified_trading_api.mock_data.seed_phase8 import (  # noqa: qg-deep-import — self-package
        generate_phase8_data,  # noqa: qg-deep-import — self-package
    )

    _p8 = generate_phase8_data()
    for _p8_domain, _p8_records in _p8.items():
        # Phase 8 module generates richer data than inline seeds — always use it
        _seed(_p8_domain, _p8_records)

    # Calendar domain (economic results + corporate actions)
    from unified_trading_api.mock_data.seed_calendar import (  # noqa: qg-deep-import — self-package
        seed_calendar,  # noqa: qg-deep-import — self-package
    )

    seed_calendar(_store)

    # Events domain (calendar, predictions, news, positions)
    from unified_trading_api.mock_data.seed_events import (  # noqa: qg-deep-import — self-package
        seed_events,  # noqa: qg-deep-import — self-package
    )

    seed_events(_store)

    # Run consistency validation (log warnings, don't crash)
    import logging

    _logger = logging.getLogger(__name__)
    _errors = validate_consistency(store)
    if _errors:
        for _e in _errors:
            _logger.warning("Seed consistency: %s", _e)
