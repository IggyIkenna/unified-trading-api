"""Seed all domains with realistic synthetic mock data.

Literal fixture records live in ``seed_data/<domain>.json`` (one file per
collection — the data SSOT, registry.py pattern: data separated from loader).
This module is the thin loader: it reads those files, derives the
cross-referenced parts in code (asset_group stamping from strategies/orders,
live/batch copies, registry-driven generators), seeds the store, and validates
cross-domain consistency. Every record carries ``org_id`` sourced from the
persona SSOT (personas.py). Distribution: odum-internal 60%, acme 20%,
vertex 12%, beta 8%.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Final, Protocol

from unified_trading_api.mock_data.personas import (  # noqa: qg-deep-import — self-package
    ORG_IDS,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.mock_data.seed_calendar import (  # noqa: qg-deep-import — self-package
    seed_calendar,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.mock_data.seed_candles import (  # noqa: qg-deep-import — self-package
    generate_candles,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.mock_data.seed_events import (  # noqa: qg-deep-import — self-package
    seed_events,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.mock_data.seed_phase8 import (  # noqa: qg-deep-import — self-package
    generate_phase8_data,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.mock_data.seed_strategies import (  # noqa: qg-deep-import — self-package
    generate_strategies,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.mock_data.seed_tickers import (  # noqa: qg-deep-import — self-package
    generate_tickers_batch,  # noqa: qg-deep-import — self-package
    generate_tickers_live,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.mock_data.seed_timeseries import (  # noqa: qg-deep-import — self-package
    generate_pnl_timeseries,  # noqa: qg-deep-import — self-package
)

# Callable type for store.list() used in validation helpers
type _ListFn = Callable[[str], list[dict[str, object]]]

SEED_VERSION: Final[str] = "4.3.0"

_logger = logging.getLogger(__name__)


class _Seedable(Protocol):
    def seed(self, collection: str, items: list[dict[str, object]]) -> None: ...


# ── Org helpers ───────────────────────────────────────────────────────
# (per-org/client literals now live in seed_data/*.json; only the default
# org is still referenced by the derivation code)
_O = "odum-internal"


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

# ── Literal fixture data — seed_data/<domain>.json per collection ────
_SEED_DATA_DIR: Final[Path] = Path(__file__).resolve().parent / "seed_data"

# Collections seeded verbatim from seed_data/<domain>.json (original
# seed order preserved). orders/fills/positions/orders_live/orders_batch/
# positions_batch/positions_live also come from JSON but get asset_group
# stamped from cross-references in seed_all_domains, so they are not here.
_LITERAL_DOMAINS: Final[tuple[str, ...]] = (
    "execution_venues",
    "algos",
    "backtests",
    "position_summary",
    "balances",
    "pnl",
    "pnl_batch",
    "pnl_live",
    "analytics_timeseries",
    "performance",
    "analytics_organizations",
    "settlements",
    "invoices",
    "fee_schedules",
    "analytics_instruments",
    "model_families",
    "experiments",
    "training_runs",
    "model_versions",
    "model_deployments",
    "ml_features",
    "datasets",
    "reports",
    "reporting_settlements",
    "reconciliation",
    "audit_events",
    "compliance",
    "data_health",
    "audit_logs",
    "system_config",
    "config_venues",
    "feature_flags",
    "alerts",
    "alert_summary",
    "risk_limits",
    "var",
    "greeks",
    "stress_tests",
    "instruments",
    "instrument_catalogue",
    "instrument_registry",
    "documents",
    "deployment_services",
    "deployments",
    "builds",
    "service_health",
    "feature_freshness",
    "activity",
    "user_organizations",
    "members",
    "subscriptions",
    "trades",
    "alerts_live",
    "alerts_batch",
    "risk_live",
    "risk_batch",
    "correlation_matrix",
    "regime",
    "exposure_types",
    "defi_health",
    "options_chain",
    "vol_surfaces",
    "fx_rates",
    "regulatory_reports",
    "news",
)


def _load_records(domain: str) -> list[dict[str, object]]:
    """Load the literal fixture records for one collection from seed_data/."""
    path = _SEED_DATA_DIR / f"{domain}.json"
    with path.open(encoding="utf-8") as fh:
        raw: object = json.load(fh)  # pyright: ignore[reportAny] — shape validated below
    if not isinstance(raw, list):
        msg = f"seed data file {path.name} must contain a JSON array of records"
        raise TypeError(msg)
    records: list[dict[str, object]] = []
    for item in raw:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, dict):
            msg = f"seed data file {path.name} must contain only JSON objects"
            raise TypeError(msg)
        records.append({str(k): v for k, v in item.items()})  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType]
    return records


def _stamp_asset_group(
    records: list[dict[str, object]],
    ref_field: str,
    asset_group_by_ref: dict[str, str],
) -> None:
    """Stamp each record's asset_group from a cross-reference map (default cefi)."""
    for rec in records:
        rec["asset_group"] = asset_group_by_ref.get(str(rec.get(ref_field)), "cefi")


def _build_strategy_configs(strategies: list[dict[str, object]]) -> list[dict[str, object]]:
    """Derive per-strategy config records from the generated strategies."""
    return [
        {
            "config_id": s["id"],
            "strategy_id": s["id"],
            "name": s["name"],
            "archetype": s.get("archetype", "unknown"),
            "asset_group": s.get("asset_group", "cefi"),
            "instruments": s.get("instruments", []),  # noqa: qg-empty-fallback — mock default for config expansion
            "execution_mode": s.get("status", "live"),
            "timeframe": "1h",
            "org_id": s.get("org_id", _O),
        }
        for s in strategies
    ]


def _check_org_integrity(
    domains: tuple[str, ...],
    list_fn: _ListFn,
) -> list[str]:
    """Return errors for records with invalid org_id values."""
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
            strategy_inception[str(s.get("id", ""))] = str(inception)  # noqa: qg-empty-fallback — sentinel key for id-less mock records

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
        live_position_ids = {str(p.get("position_id", "")) for p in live_positions}  # noqa: qg-empty-fallback — sentinel key for id-less mock records
        for bp in batch_positions:
            bp_id = str(bp.get("position_id", ""))  # noqa: qg-empty-fallback — sentinel key for id-less mock records
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
    strategy_ids = {str(s.get("id", "")) for s in strategies}  # noqa: qg-empty-fallback — sentinel key for id-less mock records

    for domain in ("positions", "orders"):
        for rec in _list(domain):
            sid = rec.get("strategy_id")
            if sid is not None and str(sid) not in strategy_ids:
                errors.append(f"{domain} record {rec.get('id', '?')} references invalid strategy_id: {sid}")

    # 2. Order reference integrity (fills → orders)
    order_ids = {str(o.get("order_id", o.get("id", ""))) for o in _list("orders")}  # noqa: qg-empty-fallback — sentinel key for id-less mock records
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

    # ── STRATEGIES (50+) — registry-driven via seed_strategies.py ─────
    _strategies = generate_strategies()
    _seed("strategies", _strategies)

    _strategy_asset_group: dict[str, str] = {str(s["id"]): str(s.get("asset_group", "cefi")) for s in _strategies}

    # Also seed strategy_configs for the config-driven expansion
    _seed("strategy_configs", _build_strategy_configs(_strategies))

    # ── ORDERS — literal records + asset_group from owning strategy ──
    _orders_records = _load_records("orders")
    _stamp_asset_group(_orders_records, "strategy_id", _strategy_asset_group)
    _seed("orders", _orders_records)

    # ── FILLS — literal records + asset_group from owning order ──────
    _order_id_to_asset_group: dict[str, str] = {
        str(o["order_id"]): str(o.get("asset_group", "cefi")) for o in _orders_records
    }
    _fills_records = _load_records("fills")
    _stamp_asset_group(_fills_records, "order_id", _order_id_to_asset_group)
    _seed("fills", _fills_records)

    # fills_live and fills_batch — copy fills data into live/batch collections
    _store_list = getattr(_store, "list", None)
    _fills_for_copy: list[dict[str, object]] = _store_list("fills") if _store_list else []
    _seed("fills_live", _fills_for_copy)
    _seed("fills_batch", [{**f, "reconciled": True} for f in _fills_for_copy])

    # ── POSITIONS (+ batch/live) — literal + asset_group stamping ────
    for _pos_domain in ("positions", "positions_batch", "positions_live"):
        _pos_records = _load_records(_pos_domain)
        _stamp_asset_group(_pos_records, "strategy_id", _strategy_asset_group)
        _seed(_pos_domain, _pos_records)

    # ── PLAIN LITERAL COLLECTIONS — seed_data/<domain>.json verbatim ─
    for _domain in _LITERAL_DOMAINS:
        _seed(_domain, _load_records(_domain))

    # ── OHLCV CANDLES — registry-driven via seed_candles.py ──────────
    _candle_data = generate_candles()
    for _interval_key, _candle_records in _candle_data.items():
        _seed(_interval_key, _candle_records)

    # Legacy "candles" alias for backwards compatibility
    _seed("candles", _candle_data.get("candles_1m", []))  # noqa: qg-empty-fallback — alias empty only if generator omits 1m

    # ── TICKERS — registry-driven via seed_tickers.py ────────────────
    _tickers_live = generate_tickers_live()
    _seed("tickers", _tickers_live)
    _seed("tickers_live", _tickers_live)
    _seed("tickers_batch", generate_tickers_batch())

    # ── ORDERS LIVE/BATCH — literal + asset_group stamping ───────────
    for _ord_domain in ("orders_live", "orders_batch"):
        _ord_records = _load_records(_ord_domain)
        _stamp_asset_group(_ord_records, "strategy_id", _strategy_asset_group)
        _seed(_ord_domain, _ord_records)

    # ── PNL TIME-SERIES — 180 daily points per strategy ──────────────
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

    # ── PHASE 8 — risk limits, options, vol, VaR, FX, regulatory ─────
    _p8 = generate_phase8_data()
    for _p8_domain, _p8_records in _p8.items():
        # Phase 8 module generates richer data than inline seeds — always use it
        _seed(_p8_domain, _p8_records)

    # Calendar domain (economic results + corporate actions)
    seed_calendar(_store)

    # Events domain (calendar, predictions, news, positions)
    seed_events(_store)

    # Run consistency validation (log warnings, don't crash)
    _errors = validate_consistency(store)
    if _errors:
        for _e in _errors:
            _logger.warning("Seed consistency: %s", _e)
