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
        resp = app_client.post(
            "/execution/orders",
            json={"instrument": "BTC-PERP", "side": "BUY", "quantity": 1, "price": 67000},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "filled"
        assert "position" in resp.json()
        assert resp.json()["position"]["instrument"] == "BTC-PERP"


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


# Remaining test classes (TestReportingRoutes through TestAdminRoutes) are in
# tests/unit/test_routes_extra.py to keep each file under 900 lines.
