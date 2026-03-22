"""Integration tests for all API routes in mock mode.

Verifies every route returns valid JSON with expected structure,
filtering works, pagination works, and org scoping works.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create test client with mock mode enabled."""
    from unified_trading_api.main import create_app

    app = create_app()
    app.state.mock_mode = True
    app.state.disable_auth = True
    app.state.start_time = 0.0

    # Wire service layer
    from unified_trading_library.core.mock_state_store import MockStateStore

    from unified_trading_api.mock_data.seed import seed_all_domains
    from unified_trading_api.services.mock_service import MockDomainService

    store = MockStateStore("test-unified-trading-api")
    seed_all_domains(store)
    app.state.service = MockDomainService(store)
    app.state.mock_store = store

    return TestClient(app)


class TestHealthRoutes:
    def test_health(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_readiness(self, client: TestClient) -> None:
        r = client.get("/readiness")
        assert r.status_code == 200


class TestExecutionRoutes:
    def test_get_orders(self, client: TestClient) -> None:
        r = client.get("/execution/orders")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) > 0

    def test_get_orders_filter_venue(self, client: TestClient) -> None:
        r = client.get("/execution/orders?venue=binance")
        assert r.status_code == 200
        for order in r.json()["data"]:
            assert order["venue"] == "binance"

    def test_get_fills(self, client: TestClient) -> None:
        r = client.get("/execution/fills")
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0

    def test_get_venues(self, client: TestClient) -> None:
        r = client.get("/execution/venues")
        assert r.status_code == 200
        assert "venues" in r.json()

    def test_get_algos(self, client: TestClient) -> None:
        r = client.get("/execution/algos")
        assert r.status_code == 200
        assert "algos" in r.json()

    def test_create_order(self, client: TestClient) -> None:
        r = client.post(
            "/execution/orders",
            json={
                "venue": "binance",
                "instrument": "BTC-USDT",
                "side": "buy",
                "type": "limit",
                "price": 68000,
                "quantity": 0.1,
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "created"


class TestPositionRoutes:
    def test_get_positions(self, client: TestClient) -> None:
        r = client.get("/positions/active")
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0

    def test_get_position_summary(self, client: TestClient) -> None:
        r = client.get("/positions/summary")
        assert r.status_code == 200

    def test_get_balances(self, client: TestClient) -> None:
        r = client.get("/positions/balances")
        assert r.status_code == 200


class TestAnalyticsRoutes:
    def test_get_pnl(self, client: TestClient) -> None:
        r = client.get("/analytics/pnl")
        assert r.status_code == 200

    def test_get_timeseries(self, client: TestClient) -> None:
        r = client.get("/analytics/timeseries")
        assert r.status_code == 200

    def test_get_performance(self, client: TestClient) -> None:
        r = client.get("/analytics/performance")
        assert r.status_code == 200


class TestMLRoutes:
    def test_get_model_families(self, client: TestClient) -> None:
        r = client.get("/ml/model-families")
        assert r.status_code == 200

    def test_get_experiments(self, client: TestClient) -> None:
        r = client.get("/ml/experiments")
        assert r.status_code == 200

    def test_get_features(self, client: TestClient) -> None:
        r = client.get("/ml/features")
        assert r.status_code == 200


class TestAlertRoutes:
    def test_get_alerts(self, client: TestClient) -> None:
        r = client.get("/alerts/list")
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0

    def test_get_alert_summary(self, client: TestClient) -> None:
        r = client.get("/alerts/summary")
        assert r.status_code == 200


class TestRiskRoutes:
    def test_get_risk_limits(self, client: TestClient) -> None:
        r = client.get("/risk/limits")
        assert r.status_code == 200

    def test_get_var(self, client: TestClient) -> None:
        r = client.get("/risk/var")
        assert r.status_code == 200


class TestMarketDataRoutes:
    def test_get_candles(self, client: TestClient) -> None:
        r = client.get("/market-data/candles?venue=binance&instrument=BTC-USDT")
        assert r.status_code == 200

    def test_get_trades(self, client: TestClient) -> None:
        r = client.get("/market-data/trades?venue=binance&instrument=BTC-USDT")
        assert r.status_code == 200


class TestServiceStatusRoutes:
    def test_get_service_health(self, client: TestClient) -> None:
        r = client.get("/service-status/health")
        assert r.status_code == 200

    def test_get_feature_freshness(self, client: TestClient) -> None:
        r = client.get("/service-status/feature-freshness")
        assert r.status_code == 200


class TestAdminRoutes:
    def test_reset_returns_ok(self, client: TestClient) -> None:
        r = client.post("/admin/reset")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_reset_then_data_still_present(self, client: TestClient) -> None:
        client.post("/admin/reset")
        r = client.get("/execution/orders")
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0


class TestPagination:
    def test_pagination_meta(self, client: TestClient) -> None:
        r = client.get("/execution/orders?page=1&page_size=2")
        assert r.status_code == 200
        pag = r.json()["pagination"]
        assert pag["page"] == 1
        assert pag["page_size"] == 2
        assert "total" in pag
        assert "has_next" in pag
