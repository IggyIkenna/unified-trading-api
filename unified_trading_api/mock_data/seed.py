"""Seed all domains with realistic synthetic mock data."""

from __future__ import annotations

from unified_trading_api.mock_data.state_store import mock_store


def seed_all_domains() -> None:
    """Populate every mock-store domain with synthetic records."""

    # ── Execution ──────────────────────────────────────────────

    mock_store.seed(
        "orders",
        [
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
            },
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
            },
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
            },
        ],
    )

    mock_store.seed(
        "fills",
        [
            {
                "fill_id": "fill-e5f6a7b8-2001",
                "order_id": "ord-a1b2c3d4-1001",
                "venue": "binance",
                "instrument": "BTC-USDT",
                "side": "buy",
                "price": 67250.50,
                "quantity": 0.15,
                "fee": 1.01,
                "fee_currency": "USDT",
                "timestamp": "2026-03-21T08:12:34Z",
            },
            {
                "fill_id": "fill-e5f6a7b8-2002",
                "order_id": "ord-a1b2c3d4-1002",
                "venue": "binance",
                "instrument": "ETH-USDT",
                "side": "sell",
                "price": 3480.25,
                "quantity": 2.0,
                "fee": 0.70,
                "fee_currency": "USDT",
                "timestamp": "2026-03-21T08:14:02Z",
            },
            {
                "fill_id": "fill-e5f6a7b8-2003",
                "order_id": "ord-a1b2c3d4-1004",
                "venue": "hyperliquid",
                "instrument": "SOL-USD-PERP",
                "side": "buy",
                "price": 145.28,
                "quantity": 25.0,
                "fee": 0.36,
                "fee_currency": "USDC",
                "timestamp": "2026-03-21T09:15:23Z",
            },
        ],
    )

    mock_store.seed(
        "execution_venues",
        [
            {
                "venue_id": "binance",
                "name": "Binance",
                "type": "cefi",
                "status": "active",
                "latency_ms": 45,
            },
            {
                "venue_id": "deribit",
                "name": "Deribit",
                "type": "cefi",
                "status": "active",
                "latency_ms": 62,
            },
            {
                "venue_id": "hyperliquid",
                "name": "Hyperliquid",
                "type": "defi",
                "status": "active",
                "latency_ms": 120,
            },
            {
                "venue_id": "uniswap_v3",
                "name": "Uniswap V3",
                "type": "defi",
                "status": "active",
                "latency_ms": 2500,
            },
            {
                "venue_id": "aave_v3",
                "name": "Aave V3",
                "type": "defi",
                "status": "active",
                "latency_ms": 3000,
            },
        ],
    )

    mock_store.seed(
        "algos",
        [
            {
                "algo_id": "twap-v2",
                "name": "TWAP",
                "description": "Time-weighted average price",
                "status": "active",
            },
            {
                "algo_id": "vwap-v1",
                "name": "VWAP",
                "description": "Volume-weighted average price",
                "status": "active",
            },
            {
                "algo_id": "iceberg-v1",
                "name": "Iceberg",
                "description": "Hidden size execution",
                "status": "active",
            },
            {
                "algo_id": "sniper-v1",
                "name": "Sniper",
                "description": "Best-bid/ask opportunistic",
                "status": "beta",
            },
        ],
    )

    mock_store.seed(
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
            },
        ],
    )

    # ── Positions ──────────────────────────────────────────────

    mock_store.seed(
        "positions",
        [
            {
                "position_id": "pos-d2e3f4a5-4001",
                "venue": "binance",
                "instrument": "BTC-USDT",
                "side": "long",
                "size": 0.50,
                "entry_price": 66800.00,
                "mark_price": 67250.50,
                "unrealized_pnl": 225.25,
                "leverage": 3.0,
            },
            {
                "position_id": "pos-d2e3f4a5-4002",
                "venue": "hyperliquid",
                "instrument": "SOL-USD-PERP",
                "side": "long",
                "size": 100.0,
                "entry_price": 143.50,
                "mark_price": 145.30,
                "unrealized_pnl": 180.00,
                "leverage": 5.0,
            },
            {
                "position_id": "pos-d2e3f4a5-4003",
                "venue": "deribit",
                "instrument": "ETH-USDT",
                "side": "short",
                "size": 5.0,
                "entry_price": 3520.00,
                "mark_price": 3480.00,
                "unrealized_pnl": 200.00,
                "leverage": 2.0,
            },
        ],
    )

    mock_store.seed(
        "position_summary",
        [
            {
                "total_positions": 3,
                "total_unrealized_pnl": 605.25,
                "total_notional": 126705.25,
                "venues_active": 3,
                "long_count": 2,
                "short_count": 1,
            },
        ],
    )

    mock_store.seed(
        "balances",
        [
            {
                "venue": "binance",
                "currency": "USDT",
                "available": 48250.00,
                "locked": 10087.50,
                "total": 58337.50,
            },
            {
                "venue": "binance",
                "currency": "BTC",
                "available": 0.50,
                "locked": 0.0,
                "total": 0.50,
            },
            {
                "venue": "hyperliquid",
                "currency": "USDC",
                "available": 22100.00,
                "locked": 7265.00,
                "total": 29365.00,
            },
            {
                "venue": "deribit",
                "currency": "ETH",
                "available": 10.0,
                "locked": 5.0,
                "total": 15.0,
            },
        ],
    )

    # ── Trading Analytics ──────────────────────────────────────

    mock_store.seed(
        "pnl",
        [
            {
                "venue": "binance",
                "realized_pnl": 1245.80,
                "unrealized_pnl": 225.25,
                "fees": 42.30,
                "date": "2026-03-21",
            },
            {
                "venue": "hyperliquid",
                "realized_pnl": 560.00,
                "unrealized_pnl": 180.00,
                "fees": 8.40,
                "date": "2026-03-21",
            },
            {
                "venue": "deribit",
                "realized_pnl": -320.50,
                "unrealized_pnl": 200.00,
                "fees": 15.60,
                "date": "2026-03-21",
            },
        ],
    )

    mock_store.seed(
        "analytics_timeseries",
        [
            {"timestamp": "2026-03-21T00:00:00Z", "equity": 87500.00, "drawdown": -0.012},
            {"timestamp": "2026-03-21T04:00:00Z", "equity": 87820.00, "drawdown": -0.008},
            {"timestamp": "2026-03-21T08:00:00Z", "equity": 88200.00, "drawdown": 0.0},
            {"timestamp": "2026-03-21T12:00:00Z", "equity": 88050.00, "drawdown": -0.002},
        ],
    )

    mock_store.seed(
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
            },
        ],
    )

    mock_store.seed(
        "analytics_organizations",
        [
            {
                "org_id": "org-f1a2b3c4-5001",
                "name": "Alpha Desk",
                "aum": 2500000.00,
                "strategies": 4,
            },
            {"org_id": "org-f1a2b3c4-5002", "name": "DeFi Desk", "aum": 800000.00, "strategies": 2},
        ],
    )

    mock_store.seed(
        "settlements",
        [
            {
                "settlement_id": "stl-a3b4c5d6-6001",
                "venue": "binance",
                "currency": "USDT",
                "amount": 5000.00,
                "status": "completed",
                "settled_at": "2026-03-20T18:00:00Z",
            },
            {
                "settlement_id": "stl-a3b4c5d6-6002",
                "venue": "deribit",
                "currency": "BTC",
                "amount": 0.08,
                "status": "pending",
                "settled_at": None,
            },
        ],
    )

    mock_store.seed(
        "analytics_instruments",
        [
            {
                "instrument": "BTC-USDT",
                "asset_class": "crypto",
                "venue": "binance",
                "volume_24h": 1250000.00,
            },
            {
                "instrument": "ETH-USDT",
                "asset_class": "crypto",
                "venue": "binance",
                "volume_24h": 780000.00,
            },
            {
                "instrument": "SOL-USD-PERP",
                "asset_class": "crypto",
                "venue": "hyperliquid",
                "volume_24h": 420000.00,
            },
        ],
    )

    # ── ML ─────────────────────────────────────────────────────

    mock_store.seed(
        "model_families",
        [
            {
                "family_id": "mf-price-forecast",
                "name": "Price Forecast",
                "framework": "pytorch",
                "versions": 3,
            },
            {
                "family_id": "mf-volatility-surface",
                "name": "Volatility Surface",
                "framework": "pytorch",
                "versions": 2,
            },
            {
                "family_id": "mf-sports-outcome",
                "name": "Sports Outcome",
                "framework": "xgboost",
                "versions": 5,
            },
        ],
    )

    mock_store.seed(
        "experiments",
        [
            {
                "experiment_id": "exp-b1c2d3e4-7001",
                "family": "mf-price-forecast",
                "name": "btc-1h-lstm-v3",
                "status": "completed",
                "best_metric": 0.0032,
                "metric_name": "mse",
                "created_at": "2026-03-19T10:00:00Z",
            },
            {
                "experiment_id": "exp-b1c2d3e4-7002",
                "family": "mf-sports-outcome",
                "name": "epl-match-xgb-v5",
                "status": "running",
                "best_metric": 0.71,
                "metric_name": "accuracy",
                "created_at": "2026-03-20T14:00:00Z",
            },
        ],
    )

    mock_store.seed(
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
            },
            {
                "run_id": "run-c2d3e4f5-8002",
                "experiment_id": "exp-b1c2d3e4-7002",
                "epoch": 30,
                "train_loss": 0.42,
                "val_loss": 0.45,
                "duration_s": 620,
                "status": "running",
            },
        ],
    )

    mock_store.seed(
        "model_versions",
        [
            {
                "version_id": "mv-d3e4f5a6-9001",
                "family": "mf-price-forecast",
                "version": "v3.1.0",
                "stage": "production",
                "created_at": "2026-03-18T12:00:00Z",
            },
            {
                "version_id": "mv-d3e4f5a6-9002",
                "family": "mf-sports-outcome",
                "version": "v5.0.0",
                "stage": "staging",
                "created_at": "2026-03-20T16:00:00Z",
            },
        ],
    )

    mock_store.seed(
        "model_deployments",
        [
            {
                "deployment_id": "dep-e4f5a6b7-0001",
                "model_version": "mv-d3e4f5a6-9001",
                "endpoint": "price-forecast-prod",
                "replicas": 2,
                "status": "serving",
                "latency_p99_ms": 28,
            },
        ],
    )

    mock_store.seed(
        "ml_features",
        [
            {
                "feature_id": "feat-rsi-14",
                "name": "rsi_14",
                "category": "technical",
                "dtype": "float64",
            },
            {
                "feature_id": "feat-vol-24h",
                "name": "volatility_24h",
                "category": "statistical",
                "dtype": "float64",
            },
            {
                "feature_id": "feat-ob-imbal",
                "name": "orderbook_imbalance",
                "category": "microstructure",
                "dtype": "float64",
            },
            {
                "feature_id": "feat-funding",
                "name": "funding_rate",
                "category": "defi",
                "dtype": "float64",
            },
        ],
    )

    mock_store.seed(
        "datasets",
        [
            {
                "dataset_id": "ds-f5a6b7c8-1001",
                "name": "btc-1h-features-2026q1",
                "rows": 2160,
                "columns": 48,
                "size_mb": 12.4,
                "created_at": "2026-03-15T08:00:00Z",
            },
            {
                "dataset_id": "ds-f5a6b7c8-1002",
                "name": "epl-match-features-2025-26",
                "rows": 760,
                "columns": 112,
                "size_mb": 4.8,
                "created_at": "2026-03-10T10:00:00Z",
            },
        ],
    )

    # ── Reporting ──────────────────────────────────────────────

    mock_store.seed(
        "reports",
        [
            {
                "report_id": "rpt-a6b7c8d9-2001",
                "report_type": "daily_pnl",
                "title": "Daily PnL Report — 2026-03-20",
                "format": "pdf",
                "status": "generated",
                "created_at": "2026-03-20T23:59:00Z",
            },
            {
                "report_id": "rpt-a6b7c8d9-2002",
                "report_type": "risk_summary",
                "title": "Weekly Risk Summary — W12 2026",
                "format": "xlsx",
                "status": "generated",
                "created_at": "2026-03-21T06:00:00Z",
            },
        ],
    )

    mock_store.seed(
        "reporting_settlements",
        [
            {
                "settlement_id": "rstl-b7c8d9e0-3001",
                "counterparty": "Binance",
                "net_amount": 4850.00,
                "currency": "USDT",
                "status": "settled",
                "date": "2026-03-20",
            },
        ],
    )

    mock_store.seed(
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
            },
            {
                "recon_id": "rcn-c8d9e0f1-4002",
                "date": "2026-03-20",
                "venue": "hyperliquid",
                "matched": 189,
                "unmatched": 0,
                "breaks": 0,
                "status": "pass",
            },
        ],
    )

    # ── Audit ──────────────────────────────────────────────────

    mock_store.seed(
        "audit_events",
        [
            {
                "event_id": "evt-d9e0f1a2-5001",
                "event_type": "ORDER_PLACED",
                "service": "execution-service",
                "user": "api-key-alpha",
                "detail": "Limit buy 0.15 BTC-USDT @ 67250.50",
                "timestamp": "2026-03-21T08:12:33Z",
            },
            {
                "event_id": "evt-d9e0f1a2-5002",
                "event_type": "CONFIG_CHANGED",
                "service": "config-service",
                "user": "admin",
                "detail": "Updated risk limit for binance:BTC-USDT",
                "timestamp": "2026-03-21T07:45:00Z",
            },
            {
                "event_id": "evt-d9e0f1a2-5003",
                "event_type": "MODEL_DEPLOYED",
                "service": "ml-inference-service",
                "user": "ml-pipeline",
                "detail": "Deployed price-forecast v3.1.0 to production",
                "timestamp": "2026-03-20T18:00:00Z",
            },
        ],
    )

    mock_store.seed(
        "compliance",
        [
            {
                "check_id": "cmp-e0f1a2b3-6001",
                "rule": "position_limit",
                "status": "pass",
                "detail": "All positions within configured limits",
                "checked_at": "2026-03-21T08:00:00Z",
            },
            {
                "check_id": "cmp-e0f1a2b3-6002",
                "rule": "wash_trade_detection",
                "status": "pass",
                "detail": "No wash trades detected in last 24h",
                "checked_at": "2026-03-21T08:00:00Z",
            },
        ],
    )

    mock_store.seed(
        "data_health",
        [
            {
                "source": "binance-ws",
                "status": "healthy",
                "last_message_at": "2026-03-21T09:29:58Z",
                "gap_count_24h": 0,
            },
            {
                "source": "deribit-ws",
                "status": "healthy",
                "last_message_at": "2026-03-21T09:29:55Z",
                "gap_count_24h": 1,
            },
            {
                "source": "hyperliquid-rest",
                "status": "degraded",
                "last_message_at": "2026-03-21T09:25:00Z",
                "gap_count_24h": 4,
            },
        ],
    )

    mock_store.seed(
        "audit_logs",
        [
            {
                "log_id": "log-f1a2b3c4-7001",
                "service": "execution-service",
                "level": "INFO",
                "message": "Order ord-a1b2c3d4-1001 filled at 67250.50",
                "timestamp": "2026-03-21T08:12:34Z",
            },
            {
                "log_id": "log-f1a2b3c4-7002",
                "service": "risk-service",
                "level": "WARN",
                "message": "Position notional approaching 80% of limit on hyperliquid",
                "timestamp": "2026-03-21T09:16:00Z",
            },
        ],
    )

    # ── Config ─────────────────────────────────────────────────

    mock_store.seed(
        "system_config",
        [
            {
                "environment": "staging",
                "cloud_provider": "gcp",
                "region": "asia-northeast1",
                "mock_mode": True,
                "max_order_rate": 100,
                "default_leverage": 3.0,
            },
        ],
    )

    mock_store.seed(
        "config_venues",
        [
            {
                "venue": "binance",
                "enabled": True,
                "api_key_configured": True,
                "rate_limit": 1200,
                "ws_enabled": True,
            },
            {
                "venue": "deribit",
                "enabled": True,
                "api_key_configured": True,
                "rate_limit": 500,
                "ws_enabled": True,
            },
            {
                "venue": "hyperliquid",
                "enabled": True,
                "api_key_configured": True,
                "rate_limit": 300,
                "ws_enabled": False,
            },
        ],
    )

    mock_store.seed(
        "feature_flags",
        [
            {
                "flag": "defi_execution",
                "enabled": True,
                "description": "Enable DeFi execution pipeline",
            },
            {
                "flag": "sports_trading",
                "enabled": True,
                "description": "Enable sports trading domain",
            },
            {"flag": "flash_loans", "enabled": False, "description": "Enable flash loan execution"},
            {
                "flag": "experimental_algos",
                "enabled": False,
                "description": "Enable experimental execution algos",
            },
        ],
    )

    # ── Alerts ─────────────────────────────────────────────────

    mock_store.seed(
        "alerts",
        [
            {
                "alert_id": "alrt-a2b3c4d5-8001",
                "severity": "high",
                "status": "active",
                "title": "Position limit 80% reached",
                "service": "risk-service",
                "instrument": "SOL-USD-PERP",
                "triggered_at": "2026-03-21T09:16:00Z",
            },
            {
                "alert_id": "alrt-a2b3c4d5-8002",
                "severity": "medium",
                "status": "active",
                "title": "Data gap detected on hyperliquid-rest",
                "service": "market-tick-data-service",
                "instrument": None,
                "triggered_at": "2026-03-21T09:25:01Z",
            },
            {
                "alert_id": "alrt-a2b3c4d5-8003",
                "severity": "low",
                "status": "acknowledged",
                "title": "Model latency p99 > 50ms",
                "service": "ml-inference-service",
                "instrument": None,
                "triggered_at": "2026-03-21T07:00:00Z",
            },
        ],
    )

    mock_store.seed(
        "alert_summary",
        [
            {"severity": "critical", "count": 0},
            {"severity": "high", "count": 1},
            {"severity": "medium", "count": 1},
            {"severity": "low", "count": 1},
        ],
    )

    # ── Risk ───────────────────────────────────────────────────

    mock_store.seed(
        "risk_limits",
        [
            {
                "venue": "binance",
                "instrument": "BTC-USDT",
                "max_position_notional": 500000.00,
                "max_order_size": 2.0,
                "max_leverage": 5.0,
                "current_utilization": 0.34,
            },
            {
                "venue": "hyperliquid",
                "instrument": "SOL-USD-PERP",
                "max_position_notional": 100000.00,
                "max_order_size": 500.0,
                "max_leverage": 10.0,
                "current_utilization": 0.73,
            },
        ],
    )

    mock_store.seed(
        "var",
        [
            {
                "portfolio": "global",
                "var_1d_99": 12500.00,
                "var_1d_95": 8200.00,
                "component_count": 3,
            },
        ],
    )

    mock_store.seed(
        "greeks",
        [
            {
                "instrument": "BTC-28MAR26-70000-C",
                "delta": 0.45,
                "gamma": 0.0012,
                "theta": -28.50,
                "vega": 142.00,
                "rho": 5.20,
            },
        ],
    )

    mock_store.seed(
        "stress_tests",
        [
            {
                "scenario": "btc_crash_20pct",
                "portfolio_impact": -17800.00,
                "worst_instrument": "BTC-USDT",
                "run_at": "2026-03-21T06:00:00Z",
            },
            {
                "scenario": "vol_spike_2x",
                "portfolio_impact": 3200.00,
                "worst_instrument": "ETH-USDT",
                "run_at": "2026-03-21T06:00:00Z",
            },
        ],
    )

    # ── Instruments ────────────────────────────────────────────

    mock_store.seed(
        "instruments",
        [
            {
                "instrument_id": "inst-b3c4d5e6-9001",
                "symbol": "BTC-USDT",
                "venue": "binance",
                "asset_class": "crypto",
                "base": "BTC",
                "quote": "USDT",
                "tick_size": 0.01,
                "lot_size": 0.00001,
                "status": "active",
            },
            {
                "instrument_id": "inst-b3c4d5e6-9002",
                "symbol": "ETH-USDT",
                "venue": "binance",
                "asset_class": "crypto",
                "base": "ETH",
                "quote": "USDT",
                "tick_size": 0.01,
                "lot_size": 0.0001,
                "status": "active",
            },
            {
                "instrument_id": "inst-b3c4d5e6-9003",
                "symbol": "SOL-USD-PERP",
                "venue": "hyperliquid",
                "asset_class": "crypto",
                "base": "SOL",
                "quote": "USD",
                "tick_size": 0.01,
                "lot_size": 0.1,
                "status": "active",
            },
            {
                "instrument_id": "inst-b3c4d5e6-9004",
                "symbol": "BTC-28MAR26-70000-C",
                "venue": "deribit",
                "asset_class": "option",
                "base": "BTC",
                "quote": "USD",
                "tick_size": 0.0005,
                "lot_size": 0.1,
                "status": "active",
            },
        ],
    )

    mock_store.seed(
        "instrument_catalogue",
        [
            {"asset_class": "crypto", "count": 45, "venues": ["binance", "deribit", "hyperliquid"]},
            {"asset_class": "option", "count": 120, "venues": ["deribit"]},
            {"asset_class": "sports", "count": 380, "venues": ["betfair", "smarkets"]},
        ],
    )

    mock_store.seed(
        "instrument_registry",
        [
            {
                "canonical": "BTC-USDT",
                "mappings": {
                    "binance": "BTCUSDT",
                    "deribit": "BTC-USDT",
                    "hyperliquid": "BTC",
                },
            },
            {
                "canonical": "ETH-USDT",
                "mappings": {
                    "binance": "ETHUSDT",
                    "deribit": "ETH-USDT",
                    "hyperliquid": "ETH",
                },
            },
        ],
    )

    # ── Documents ──────────────────────────────────────────────

    mock_store.seed(
        "documents",
        [
            {
                "document_id": "doc-c4d5e6f7-0001",
                "filename": "daily-risk-report-2026-03-20.pdf",
                "category": "risk",
                "size_bytes": 245000,
                "uploaded_at": "2026-03-20T23:59:30Z",
            },
            {
                "document_id": "doc-c4d5e6f7-0002",
                "filename": "trade-blotter-2026-03-20.csv",
                "category": "execution",
                "size_bytes": 82000,
                "uploaded_at": "2026-03-20T23:58:00Z",
            },
        ],
    )

    # ── Deployment ─────────────────────────────────────────────

    mock_store.seed(
        "deployment_services",
        [
            {
                "service": "execution-service",
                "version": "0.4.12",
                "replicas": 2,
                "status": "running",
                "region": "asia-northeast1",
            },
            {
                "service": "strategy-service",
                "version": "0.3.8",
                "replicas": 1,
                "status": "running",
                "region": "asia-northeast1",
            },
            {
                "service": "risk-service",
                "version": "0.2.5",
                "replicas": 1,
                "status": "running",
                "region": "asia-northeast1",
            },
            {
                "service": "market-tick-data-service",
                "version": "0.5.1",
                "replicas": 3,
                "status": "running",
                "region": "asia-northeast1",
            },
            {
                "service": "alerting-service",
                "version": "0.3.2",
                "replicas": 1,
                "status": "running",
                "region": "asia-northeast1",
            },
        ],
    )

    mock_store.seed(
        "deployments",
        [
            {
                "deployment_id": "dpl-d5e6f7a8-1001",
                "service": "execution-service",
                "version": "0.4.12",
                "status": "active",
                "deployed_at": "2026-03-20T10:00:00Z",
                "deployed_by": "ci-pipeline",
            },
            {
                "deployment_id": "dpl-d5e6f7a8-1002",
                "service": "market-tick-data-service",
                "version": "0.5.1",
                "status": "active",
                "deployed_at": "2026-03-19T14:00:00Z",
                "deployed_by": "ci-pipeline",
            },
        ],
    )

    mock_store.seed(
        "builds",
        [
            {
                "build_id": "bld-e6f7a8b9-2001",
                "service": "execution-service",
                "version": "0.4.12",
                "status": "success",
                "duration_s": 142,
                "started_at": "2026-03-20T09:55:00Z",
            },
            {
                "build_id": "bld-e6f7a8b9-2002",
                "service": "strategy-service",
                "version": "0.3.9",
                "status": "failed",
                "duration_s": 88,
                "started_at": "2026-03-21T08:00:00Z",
            },
        ],
    )

    # ── Service Status ─────────────────────────────────────────

    mock_store.seed(
        "service_health",
        [
            {
                "service": "execution-service",
                "status": "healthy",
                "uptime_pct": 99.98,
                "last_check": "2026-03-21T09:30:00Z",
            },
            {
                "service": "strategy-service",
                "status": "healthy",
                "uptime_pct": 99.95,
                "last_check": "2026-03-21T09:30:00Z",
            },
            {
                "service": "risk-service",
                "status": "healthy",
                "uptime_pct": 99.99,
                "last_check": "2026-03-21T09:30:00Z",
            },
            {
                "service": "market-tick-data-service",
                "status": "degraded",
                "uptime_pct": 98.50,
                "last_check": "2026-03-21T09:30:00Z",
            },
            {
                "service": "alerting-service",
                "status": "healthy",
                "uptime_pct": 99.97,
                "last_check": "2026-03-21T09:30:00Z",
            },
        ],
    )

    mock_store.seed(
        "feature_freshness",
        [
            {
                "pipeline": "technical-features",
                "last_computed": "2026-03-21T09:28:00Z",
                "staleness_s": 120,
                "status": "fresh",
            },
            {
                "pipeline": "onchain-features",
                "last_computed": "2026-03-21T09:15:00Z",
                "staleness_s": 900,
                "status": "fresh",
            },
            {
                "pipeline": "sports-features",
                "last_computed": "2026-03-21T08:00:00Z",
                "staleness_s": 5400,
                "status": "stale",
            },
        ],
    )

    mock_store.seed(
        "activity",
        [
            {
                "event": "Order filled",
                "detail": "BTC-USDT buy 0.15 @ 67250.50",
                "service": "execution-service",
                "timestamp": "2026-03-21T08:12:34Z",
            },
            {
                "event": "Model deployed",
                "detail": "price-forecast v3.1.0 → production",
                "service": "ml-inference-service",
                "timestamp": "2026-03-20T18:00:00Z",
            },
            {
                "event": "Alert triggered",
                "detail": "Position limit 80% on SOL-USD-PERP",
                "service": "risk-service",
                "timestamp": "2026-03-21T09:16:00Z",
            },
            {
                "event": "Build failed",
                "detail": "strategy-service v0.3.9 build failed",
                "service": "deployment-service",
                "timestamp": "2026-03-21T08:01:28Z",
            },
        ],
    )

    # ── Users ──────────────────────────────────────────────────

    mock_store.seed(
        "user_organizations",
        [
            {
                "org_id": "org-f7a8b9c0-3001",
                "name": "Unified Trading Corp",
                "plan": "enterprise",
                "member_count": 8,
            },
        ],
    )

    mock_store.seed(
        "members",
        [
            {
                "member_id": "usr-a8b9c0d1-4001",
                "organization_id": "org-f7a8b9c0-3001",
                "email": "alice@unified-trading.io",
                "role": "admin",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4002",
                "organization_id": "org-f7a8b9c0-3001",
                "email": "bob@unified-trading.io",
                "role": "trader",
                "status": "active",
            },
            {
                "member_id": "usr-a8b9c0d1-4003",
                "organization_id": "org-f7a8b9c0-3001",
                "email": "carol@unified-trading.io",
                "role": "viewer",
                "status": "active",
            },
        ],
    )

    mock_store.seed(
        "subscriptions",
        [
            {
                "subscription_id": "sub-b9c0d1e2-5001",
                "organization_id": "org-f7a8b9c0-3001",
                "plan": "enterprise",
                "status": "active",
                "started_at": "2025-12-01T00:00:00Z",
                "renews_at": "2026-12-01T00:00:00Z",
                "features": ["execution", "analytics", "ml", "risk", "defi"],
            },
        ],
    )

    # ── Market Data (for existing route) ───────────────────────

    mock_store.seed(
        "candles",
        [
            {
                "timestamp": "2026-03-21T09:00:00Z",
                "open": 67100.00,
                "high": 67300.00,
                "low": 67050.00,
                "close": 67250.50,
                "volume": 142.5,
            },
            {
                "timestamp": "2026-03-21T09:01:00Z",
                "open": 67250.50,
                "high": 67280.00,
                "low": 67200.00,
                "close": 67220.00,
                "volume": 88.3,
            },
        ],
    )

    mock_store.seed(
        "trades",
        [
            {
                "trade_id": "t-001",
                "price": 67250.50,
                "quantity": 0.15,
                "side": "buy",
                "timestamp": "2026-03-21T09:00:12Z",
            },
            {
                "trade_id": "t-002",
                "price": 67248.00,
                "quantity": 0.30,
                "side": "sell",
                "timestamp": "2026-03-21T09:00:14Z",
            },
        ],
    )

    mock_store.seed(
        "tickers",
        [
            {
                "instrument": "BTC-USDT",
                "bid": 67248.00,
                "ask": 67250.50,
                "last": 67250.50,
                "volume_24h": 18500.0,
            },
            {
                "instrument": "ETH-USDT",
                "bid": 3479.50,
                "ask": 3480.25,
                "last": 3480.00,
                "volume_24h": 92000.0,
            },
        ],
    )
