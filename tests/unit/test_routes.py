"""Tests for all route modules.

Uses the app_client fixture from conftest.py which provides a TestClient
with mock mode + auth disabled + an in-memory service.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class TestAlertRoutes:
    def test_get_alerts_list(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "alerts_live",
            [
                {"id": "a1", "severity": "high", "status": "active", "acknowledged": False},
                {"id": "a2", "severity": "low", "status": "active", "acknowledged": True},
            ],
        )
        resp = app_client.get("/alerts/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "live"
        assert len(data["data"]) == 2

    def test_get_alerts_with_filters(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "alerts_live",
            [
                {"id": "a1", "severity": "high", "status": "active", "acknowledged": False},
                {"id": "a2", "severity": "low", "status": "active", "acknowledged": True},
            ],
        )
        resp = app_client.get("/alerts/list?severity=high")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_get_alert_summary(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("alert_summary", [{"critical": 2, "high": 5}])
        resp = app_client.get("/alerts/summary")
        assert resp.status_code == 200
        assert "summary" in resp.json()

    def test_acknowledge_alert_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "alerts_live",
            [
                {"id": "a1", "severity": "high", "status": "active"},
            ],
        )
        resp = app_client.post("/alerts/a1/acknowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert "alert" in data

    def test_acknowledge_alert_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post("/alerts/nonexistent/acknowledge")
        assert resp.status_code == 200
        assert "error" in resp.json()
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_escalate_alert_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "alerts_live",
            [
                {"id": "a1", "severity": "medium", "status": "active"},
            ],
        )
        resp = app_client.post("/alerts/a1/escalate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "escalated"

    def test_escalate_alert_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post("/alerts/nonexistent/escalate")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_active_alerts(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "alerts_live",
            [
                {"id": "a1", "severity": "high", "acknowledged": False},
                {"id": "a2", "severity": "low", "acknowledged": True},
            ],
        )
        resp = app_client.get("/alerts/active")
        assert resp.status_code == 200

    def test_get_active_alerts_acknowledged_filter(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "alerts_live",
            [
                {"id": "a1", "severity": "high", "acknowledged": False},
                {"id": "a2", "severity": "low", "acknowledged": True},
            ],
        )
        resp = app_client.get("/alerts/active?acknowledged=false")
        assert resp.status_code == 200

    def test_resolve_alert_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "alerts_live",
            [
                {"id": "a1", "status": "active"},
            ],
        )
        resp = app_client.post("/alerts/a1/resolve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_resolve_alert_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post("/alerts/nonexistent/resolve")
        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------


class TestInstrumentRoutes:
    def test_get_instruments(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "instruments",
            [
                {"id": "i1", "symbol": "BTC-PERP", "venue": "binance", "asset_class": "crypto"},
            ],
        )
        resp = app_client.get("/instruments/list")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_get_instruments_with_filter(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "instruments",
            [
                {"id": "i1", "venue": "binance", "asset_class": "crypto"},
                {"id": "i2", "venue": "okx", "asset_class": "crypto"},
            ],
        )
        resp = app_client.get("/instruments/list?venue=binance")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_get_catalogue(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("instrument_catalogue", [{"id": "cat1"}])
        resp = app_client.get("/instruments/catalogue")
        assert resp.status_code == 200
        assert "catalogue" in resp.json()

    def test_get_registry(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("instrument_registry", [{"id": "reg1"}])
        resp = app_client.get("/instruments/registry")
        assert resp.status_code == 200
        assert "registry" in resp.json()

    def test_mock_mode_guard(self, app_client: TestClient) -> None:
        """Mock CRUD endpoints should work in mock mode."""
        resp = app_client.post(
            "/instruments/mock/create",
            json={
                "venue": "BINANCE",
                "instrument_type": "PERPETUAL",
                "symbol": "TEST-PERP",
                "base_asset": "TEST",
                "quote_asset": "USD",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_mock_mode_guard_non_mock(self) -> None:
        """Mock endpoints should return 403 when not in mock mode."""
        from tests.unit.conftest import InMemoryService
        from unified_trading_api.main import create_app

        app = create_app()
        svc = InMemoryService()
        app.state.mock_mode = False
        app.state.disable_auth = True
        app.state.start_time = 0.0
        app.state.service = svc
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/instruments/mock/create",
            json={"venue": "binance", "instrument_type": "PERPETUAL", "symbol": "X"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Trading Analytics
# ---------------------------------------------------------------------------


class TestTradingAnalyticsRoutes:
    def test_get_pnl(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("pnl_live", [{"id": "p1", "strategy": "alpha", "pnl": 100}])
        resp = app_client.get("/analytics/pnl")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "live"
        assert data["period"] == "1d"

    def test_get_pnl_batch_mode(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("pnl_batch", [{"id": "p1", "pnl": 200}])
        resp = app_client.get("/analytics/pnl?mode=batch")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "batch"

    def test_get_timeseries(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("pnl_timeseries_live", [{"id": "t1", "value": 100}])
        resp = app_client.get("/analytics/timeseries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "equity"
        assert data["granularity"] == "1h"

    def test_get_performance(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("performance", [{"id": "perf1", "sharpe": 2.1}])
        resp = app_client.get("/analytics/performance")
        assert resp.status_code == 200
        assert "performance" in resp.json()

    def test_get_organizations(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("analytics_organizations", [{"id": "org1"}])
        resp = app_client.get("/analytics/organizations")
        assert resp.status_code == 200

    def test_get_settlements(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("settlements", [{"id": "s1", "status": "settled"}])
        resp = app_client.get("/analytics/settlements")
        assert resp.status_code == 200

    def test_get_analytics_instruments(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("analytics_instruments", [{"id": "ai1", "asset_class": "crypto"}])
        resp = app_client.get("/analytics/instruments")
        assert resp.status_code == 200

    def test_create_pnl_snapshot(self, app_client: TestClient) -> None:
        resp = app_client.post("/analytics/pnl", json={"strategy": "alpha"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_create_timeseries_entry(self, app_client: TestClient) -> None:
        resp = app_client.post("/analytics/timeseries", json={"value": 42})
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_create_performance_snapshot(self, app_client: TestClient) -> None:
        resp = app_client.post("/analytics/performance", json={"sharpe": 1.5})
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_create_settlement(self, app_client: TestClient) -> None:
        resp = app_client.post("/analytics/settlements", json={"venue": "binance"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_get_strategies(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "strategies",
            [
                {"id": "s1", "name": "Alpha", "status": "live", "asset_class": "crypto"},
            ],
        )
        resp = app_client.get("/analytics/strategies")
        assert resp.status_code == 200

    def test_get_strategy_detail_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("strategies", [{"id": "s1", "name": "Alpha"}])
        resp = app_client.get("/analytics/strategies/s1")
        assert resp.status_code == 200
        assert "strategy" in resp.json()

    def test_get_strategy_detail_not_found(self, app_client: TestClient) -> None:
        resp = app_client.get("/analytics/strategies/nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_promote_strategy_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("strategies", [{"id": "s1", "status": "staging"}])
        resp = app_client.post("/analytics/strategies/s1/promote")
        assert resp.status_code == 200
        assert resp.json()["status"] == "promoted"

    def test_promote_strategy_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post("/analytics/strategies/nonexistent/promote")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_reject_strategy_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("strategies", [{"id": "s1", "status": "staging"}])
        resp = app_client.post("/analytics/strategies/s1/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_strategy_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post("/analytics/strategies/nonexistent/reject")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_scale_strategy(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("strategies", [{"id": "s1", "status": "live"}])
        resp = app_client.post("/analytics/strategies/s1/scale", json={"scale_factor": 1.5})
        assert resp.status_code == 200
        assert resp.json()["status"] == "scaled"
        assert resp.json()["scale_factor"] == 1.5

    def test_scale_strategy_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/analytics/strategies/nonexistent/scale", json={"scale_factor": 2.0}
        )
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_strategy_configs(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("strategies", [{"id": "s1"}])
        resp = app_client.get("/analytics/strategy-configs")
        assert resp.status_code == 200
        assert "configs" in resp.json()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class TestExecutionRoutes:
    def test_get_orders(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("orders_live", [{"id": "o1", "status": "filled"}])
        resp = app_client.get("/execution/orders")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

    def test_get_fills(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("fills_live", [{"id": "f1", "venue": "binance"}])
        resp = app_client.get("/execution/fills")
        assert resp.status_code == 200

    def test_get_fills_fallback(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        """When fills_live is empty, falls back to 'fills' collection."""
        mock_service.seed("fills", [{"id": "f1"}])
        resp = app_client.get("/execution/fills")
        assert resp.status_code == 200

    def test_get_venues(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("execution_venues", [{"id": "v1", "name": "binance"}])
        resp = app_client.get("/execution/venues")
        assert resp.status_code == 200

    def test_get_algos(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("algos", [{"id": "twap"}])
        resp = app_client.get("/execution/algos")
        assert resp.status_code == 200

    def test_get_backtests(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("backtests", [{"id": "bt1"}])
        resp = app_client.get("/execution/backtests")
        assert resp.status_code == 200

    def test_create_order(self, app_client: TestClient) -> None:
        resp = app_client.post("/execution/orders", json={"symbol": "BTC-PERP", "side": "BUY"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


class TestPositionRoutes:
    def test_get_active_positions(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("positions_live", [{"id": "p1", "venue": "binance"}])
        resp = app_client.get("/positions/active")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

    def test_get_position_summary(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("position_summary", [{"total_value": 1000}])
        resp = app_client.get("/positions/summary")
        assert resp.status_code == 200

    def test_get_balances(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("balances", [{"id": "b1", "venue": "binance"}])
        resp = app_client.get("/positions/balances")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Market Data
# ---------------------------------------------------------------------------


class TestMarketDataRoutes:
    def test_get_candles(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("candles", [{"id": "c1", "instrument": "BTC-PERP"}])
        resp = app_client.get("/market-data/candles?instrument=BTC-PERP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instrument"] == "BTC-PERP"

    def test_get_candles_different_interval(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("candles_4h", [{"id": "c1", "instrument": "BTC-PERP"}])
        resp = app_client.get("/market-data/candles?instrument=BTC-PERP&interval=4h")
        assert resp.status_code == 200

    def test_get_orderbook(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("tickers_live", [{"id": "t1", "instrument": "BTC-PERP", "price": 67000}])
        resp = app_client.get("/market-data/orderbook?instrument=BTC-PERP&depth=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "bids" in data
        assert "asks" in data

    def test_get_orderbook_no_tickers(self, app_client: TestClient) -> None:
        """Orderbook falls back to 100.0 mid price when no tickers."""
        resp = app_client.get("/market-data/orderbook?instrument=UNKNOWN&depth=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mid_price"] == 100.0

    def test_get_trades(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("trades", [{"id": "tr1"}])
        resp = app_client.get("/market-data/trades?venue=binance&instrument=BTC-PERP")
        assert resp.status_code == 200

    def test_get_tickers(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("tickers", [{"id": "t1"}])
        resp = app_client.get("/market-data/tickers?venue=binance")
        assert resp.status_code == 200

    def test_get_fx_rates_with_data(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("fx_rates", [{"id": "fx1", "pair": "BTC/USD", "rate": 67000}])
        resp = app_client.get("/market-data/fx-rates")
        assert resp.status_code == 200

    def test_get_fx_rates_fallback(self, app_client: TestClient) -> None:
        """When no fx_rates seeded, returns static fallback."""
        resp = app_client.get("/market-data/fx-rates")
        assert resp.status_code == 200
        rates = resp.json()["rates"]
        assert len(rates) == 5


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


class TestRiskRoutes:
    def test_get_exposure(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("risk_live", [{"id": "r1", "strategy_id": "s1"}])
        resp = app_client.get("/risk/exposure")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

    def test_get_limits(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("risk_limits", [{"id": "rl1", "venue": "binance"}])
        resp = app_client.get("/risk/limits")
        assert resp.status_code == 200

    def test_get_var(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("var", [{"id": "v1"}])
        resp = app_client.get("/risk/var")
        assert resp.status_code == 200
        assert resp.json()["confidence"] == 0.99

    def test_get_greeks(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("greeks", [{"id": "g1"}])
        resp = app_client.get("/risk/greeks")
        assert resp.status_code == 200

    def test_get_stress_tests(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("stress_tests", [{"id": "st1"}])
        resp = app_client.get("/risk/stress")
        assert resp.status_code == 200

    def test_circuit_breaker_trip(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("strategies", [{"id": "s1", "status": "active"}])
        resp = app_client.post(
            "/risk/circuit-breaker", json={"strategy_id": "s1", "action": "trip"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_circuit_breaker_reset(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("strategies", [{"id": "s1", "status": "tripped"}])
        resp = app_client.post(
            "/risk/circuit-breaker", json={"strategy_id": "s1", "action": "reset"}
        )
        assert resp.status_code == 200

    def test_circuit_breaker_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post("/risk/circuit-breaker", json={"strategy_id": "nonexistent"})
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_kill_switch_strategy(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("strategies", [{"id": "s1", "status": "live"}])
        resp = app_client.post("/risk/kill-switch", json={"scope": "strategy", "target_id": "s1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_kill_switch_strategy_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/risk/kill-switch", json={"scope": "strategy", "target_id": "nonexistent"}
        )
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_kill_switch_global(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "strategies",
            [
                {"id": "s1", "status": "live"},
                {"id": "s2", "status": "live"},
            ],
        )
        resp = app_client.post("/risk/kill-switch", json={"scope": "global"})
        assert resp.status_code == 200
        assert resp.json()["strategies_halted"] == 2

    def test_kill_switch_venue(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "strategies",
            [
                {"id": "s1", "venue": "binance", "status": "live"},
            ],
        )
        resp = app_client.post("/risk/kill-switch", json={"scope": "venue", "target_id": "binance"})
        assert resp.status_code == 200

    def test_kill_switch_invalid_scope(self, app_client: TestClient) -> None:
        resp = app_client.post("/risk/kill-switch", json={"scope": "invalid"})
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_var_summary(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("var", [{"id": "v1"}])
        resp = app_client.get("/risk/var-summary")
        assert resp.status_code == 200

    def test_get_stress_test(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("stress_tests", [{"id": "st1", "scenario": "crash"}])
        resp = app_client.get("/risk/stress-test")
        assert resp.status_code == 200

    def test_get_correlation_matrix(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("correlation_matrix", [{"id": "cm1"}])
        resp = app_client.get("/risk/correlation-matrix")
        assert resp.status_code == 200

    def test_get_regime_with_data(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("regime", [{"id": "r1", "regime": "high_vol", "multiplier": 1.5}])
        resp = app_client.get("/risk/regime")
        assert resp.status_code == 200
        assert resp.json()["regime"] == "high_vol"

    def test_get_regime_fallback(self, app_client: TestClient) -> None:
        resp = app_client.get("/risk/regime")
        assert resp.status_code == 200
        assert resp.json()["regime"] == "normal"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


class TestReportingRoutes:
    def test_get_reports(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("reports", [{"id": "r1", "report_type": "daily"}])
        resp = app_client.get("/reporting/reports")
        assert resp.status_code == 200

    def test_get_settlements(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("reporting_settlements", [{"id": "s1"}])
        resp = app_client.get("/reporting/settlements")
        assert resp.status_code == 200

    def test_get_reconciliation(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("reconciliation", [{"id": "rec1"}])
        resp = app_client.get("/reporting/reconciliation")
        assert resp.status_code == 200

    def test_get_regulatory(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("regulatory_reports", [{"id": "reg1"}])
        resp = app_client.get("/reporting/regulatory")
        assert resp.status_code == 200

    def test_generate_report(self, app_client: TestClient) -> None:
        resp = app_client.post("/reporting/generate", json={"report_type": "pnl"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_download_report_not_found(self, app_client: TestClient) -> None:
        resp = app_client.get("/reporting/download/nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_download_report_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("generated_reports", [{"id": "rpt1", "title": "Test"}])
        resp = app_client.get("/reporting/download/rpt1")
        assert resp.status_code == 200

    def test_create_schedule(self, app_client: TestClient) -> None:
        resp = app_client.post("/reporting/schedules", json={"frequency": "daily"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_get_schedules(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("scheduled_reports", [{"id": "sched1"}])
        resp = app_client.get("/reporting/schedules")
        assert resp.status_code == 200

    def test_get_pnl_attribution(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("pnl_attribution", [{"id": "pa1", "period": "1d"}])
        resp = app_client.get("/reporting/pnl-attribution")
        assert resp.status_code == 200

    def test_get_executive_summary(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("executive_summary", [{"id": "es1", "period": "1d", "aum": 1000000}])
        resp = app_client.get("/reporting/executive-summary")
        assert resp.status_code == 200

    def test_get_executive_summary_empty(self, app_client: TestClient) -> None:
        resp = app_client.get("/reporting/executive-summary")
        assert resp.status_code == 200
        assert resp.json()["summary"] == {}

    def test_get_invoices(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("invoices", [{"id": "inv1"}])
        resp = app_client.get("/reporting/invoices")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# ML
# ---------------------------------------------------------------------------


class TestMLRoutes:
    def test_get_model_families(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("model_families", [{"id": "mf1"}])
        resp = app_client.get("/ml/model-families")
        assert resp.status_code == 200

    def test_get_experiments(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("experiments", [{"id": "e1"}])
        resp = app_client.get("/ml/experiments")
        assert resp.status_code == 200

    def test_get_training_runs(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("training_runs", [{"id": "tr1"}])
        resp = app_client.get("/ml/training-runs")
        assert resp.status_code == 200

    def test_get_model_versions(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("model_versions", [{"id": "mv1"}])
        resp = app_client.get("/ml/versions")
        assert resp.status_code == 200

    def test_get_model_deployments(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("model_deployments", [{"id": "md1"}])
        resp = app_client.get("/ml/deployments")
        assert resp.status_code == 200

    def test_get_features(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("ml_features", [{"id": "f1"}])
        resp = app_client.get("/ml/features")
        assert resp.status_code == 200

    def test_get_datasets(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("datasets", [{"id": "d1"}])
        resp = app_client.get("/ml/datasets")
        assert resp.status_code == 200

    def test_get_training_jobs(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("training_runs", [{"id": "tj1", "status": "running"}])
        resp = app_client.get("/ml/training-jobs")
        assert resp.status_code == 200

    def test_create_training_job(self, app_client: TestClient) -> None:
        resp = app_client.post("/ml/training-jobs", json={"model": "alpha", "epochs": 100})
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_get_validation_results(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("validation_results", [{"id": "vr1"}])
        resp = app_client.get("/ml/validation-results")
        assert resp.status_code == 200

    def test_promote_model_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("model_versions", [{"id": "mv1", "status": "staging"}])
        resp = app_client.post("/ml/models/mv1/promote")
        assert resp.status_code == 200
        assert resp.json()["status"] == "promoted"

    def test_promote_model_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post("/ml/models/nonexistent/promote")
        assert resp.status_code == 200
        assert "error" in resp.json()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfigRoutes:
    def test_get_system_config(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("system_config", [{"id": "cfg1", "mode": "mock"}])
        resp = app_client.get("/config/system")
        assert resp.status_code == 200

    def test_get_system_config_empty(self, app_client: TestClient) -> None:
        resp = app_client.get("/config/system")
        assert resp.status_code == 200
        assert resp.json()["config"] == {}

    def test_update_system_config_create(self, app_client: TestClient) -> None:
        resp = app_client.put("/config/system", json={"theme": "dark"})
        assert resp.status_code == 200

    def test_update_system_config_update(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("system_config", [{"id": "", "mode": "mock"}])
        resp = app_client.put("/config/system", json={"mode": "real"})
        assert resp.status_code == 200

    def test_get_venues(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("config_venues", [{"id": "v1"}])
        resp = app_client.get("/config/venues")
        assert resp.status_code == 200

    def test_get_feature_flags(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("feature_flags", [{"id": "ff1", "enabled": True}])
        resp = app_client.get("/config/feature-flags")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestAuditRoutes:
    def test_get_audit_events(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("audit_events", [{"id": "ae1", "event_type": "login"}])
        resp = app_client.get("/audit/events")
        assert resp.status_code == 200

    def test_get_compliance(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("compliance", [{"id": "c1"}])
        resp = app_client.get("/audit/compliance")
        assert resp.status_code == 200

    def test_get_data_health(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("data_health", [{"id": "dh1"}])
        resp = app_client.get("/audit/data-health")
        assert resp.status_code == 200

    def test_get_audit_logs(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("audit_logs", [{"id": "al1"}])
        resp = app_client.get("/audit/logs")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------


class TestDeploymentRoutes:
    def test_get_services(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("deployment_services", [{"id": "ds1"}])
        resp = app_client.get("/deployment/services")
        assert resp.status_code == 200

    def test_get_deployments(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("deployments", [{"id": "d1"}])
        resp = app_client.get("/deployment/deployments")
        assert resp.status_code == 200

    def test_get_builds(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("builds", [{"id": "b1"}])
        resp = app_client.get("/deployment/builds")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class TestDocumentRoutes:
    def test_get_upload_url(self, app_client: TestClient) -> None:
        resp = app_client.get("/documents/upload-url?filename=report.pdf")
        assert resp.status_code == 200
        assert "upload_url" in resp.json()

    def test_get_download_url_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("documents", [{"id": "doc1", "name": "report.pdf"}])
        resp = app_client.get("/documents/download-url?document_id=doc1")
        assert resp.status_code == 200
        assert "download_url" in resp.json()

    def test_get_download_url_not_found(self, app_client: TestClient) -> None:
        resp = app_client.get("/documents/download-url?document_id=nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_list_documents(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("documents", [{"id": "doc1"}])
        resp = app_client.get("/documents/list")
        assert resp.status_code == 200

    def test_delete_document_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("documents", [{"id": "doc1"}])
        resp = app_client.delete("/documents/doc1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_document_not_found(self, app_client: TestClient) -> None:
        resp = app_client.delete("/documents/nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()


# ---------------------------------------------------------------------------
# Derivatives
# ---------------------------------------------------------------------------


class TestDerivativesRoutes:
    def test_get_options_chain(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("options_chain", [{"id": "oc1", "underlying": "BTC", "venue": "deribit"}])
        resp = app_client.get("/derivatives/options-chain")
        assert resp.status_code == 200

    def test_get_vol_surface(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("vol_surfaces", [{"id": "vs1", "underlying": "BTC"}])
        resp = app_client.get("/derivatives/vol-surface")
        assert resp.status_code == 200

    def test_get_portfolio_greeks_with_data(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("portfolio_greeks", [{"id": "pg1", "delta": 0.5}])
        resp = app_client.get("/derivatives/portfolio-greeks")
        assert resp.status_code == 200

    def test_get_portfolio_greeks_empty(self, app_client: TestClient) -> None:
        resp = app_client.get("/derivatives/portfolio-greeks")
        assert resp.status_code == 200
        greeks = resp.json()["greeks"]
        assert greeks["delta"] == 0.0


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


class TestComplianceRoutes:
    def test_pre_trade_check(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "risk_limits",
            [
                {"id": "rl1", "strategy_id": "s1", "max_position_size": 1000000},
            ],
        )
        mock_service.seed("positions", [])
        resp = app_client.post(
            "/compliance/pre-trade-check",
            json={
                "instrument": "BTC-PERP",
                "side": "BUY",
                "quantity": 1,
                "price": 67000,
                "strategy_id": "s1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "approved" in data
        assert "checks" in data
        assert len(data["checks"]) == 6


# ---------------------------------------------------------------------------
# Service Status
# ---------------------------------------------------------------------------


class TestServiceStatusRoutes:
    def test_get_service_health(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("service_health", [{"id": "sh1", "service": "execution"}])
        resp = app_client.get("/service-status/health")
        assert resp.status_code == 200

    def test_get_feature_freshness(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("feature_freshness", [{"id": "ff1"}])
        resp = app_client.get("/service-status/feature-freshness")
        assert resp.status_code == 200

    def test_get_activity(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("activity", [{"id": "act1"}])
        resp = app_client.get("/service-status/activity")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestUserRoutes:
    def test_get_organizations(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("user_organizations", [{"id": "org1"}])
        resp = app_client.get("/users/organizations")
        assert resp.status_code == 200

    def test_get_members(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("members", [{"id": "m1"}])
        resp = app_client.get("/users/members")
        assert resp.status_code == 200

    def test_get_subscriptions(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("subscriptions", [{"id": "sub1"}])
        resp = app_client.get("/users/subscriptions")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class TestAdminRoutes:
    def test_reset_mock_mode(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        """Reset in mock mode should succeed."""
        resp = app_client.post("/admin/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_reset_non_mock_mode(self) -> None:
        """Reset in non-mock mode should return forbidden."""
        from tests.unit.conftest import InMemoryService
        from unified_trading_api.main import create_app

        app = create_app()
        svc = InMemoryService()
        app.state.mock_mode = False
        app.state.disable_auth = True
        app.state.start_time = 0.0
        app.state.service = svc
        client = TestClient(app)
        resp = client.post("/admin/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "forbidden"
