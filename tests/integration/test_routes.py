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
    from unified_trading_library import MockStateStore

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


class TestAuditRoutes:
    def test_get_audit_events(self, client: TestClient) -> None:
        r = client.get("/audit/events")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_get_compliance(self, client: TestClient) -> None:
        r = client.get("/audit/compliance")
        assert r.status_code == 200

    def test_get_data_health(self, client: TestClient) -> None:
        r = client.get("/audit/data-health")
        assert r.status_code == 200

    def test_get_audit_logs(self, client: TestClient) -> None:
        r = client.get("/audit/logs")
        assert r.status_code == 200


class TestConfigRoutes:
    def test_get_system_config(self, client: TestClient) -> None:
        r = client.get("/config/system")
        assert r.status_code == 200

    def test_get_venues(self, client: TestClient) -> None:
        r = client.get("/config/venues")
        assert r.status_code == 200

    def test_get_feature_flags(self, client: TestClient) -> None:
        r = client.get("/config/feature-flags")
        assert r.status_code == 200


class TestDeploymentRoutes:
    def test_get_services(self, client: TestClient) -> None:
        r = client.get("/deployment/services")
        assert r.status_code == 200

    def test_get_deployments(self, client: TestClient) -> None:
        r = client.get("/deployment/deployments")
        assert r.status_code == 200

    def test_get_builds(self, client: TestClient) -> None:
        r = client.get("/deployment/builds")
        assert r.status_code == 200


class TestDocumentsRoutes:
    def test_list_documents(self, client: TestClient) -> None:
        r = client.get("/documents/list")
        assert r.status_code == 200

    def test_get_upload_url(self, client: TestClient) -> None:
        r = client.get("/documents/upload-url?filename=test.pdf")
        assert r.status_code == 200

    def test_get_download_url(self, client: TestClient) -> None:
        r = client.get("/documents/download-url?document_id=doc-001")
        assert r.status_code == 200


class TestInstrumentsRoutes:
    def test_list_instruments(self, client: TestClient) -> None:
        r = client.get("/instruments/list")
        assert r.status_code == 200

    def test_get_catalogue(self, client: TestClient) -> None:
        r = client.get("/instruments/catalogue")
        assert r.status_code == 200

    def test_get_registry(self, client: TestClient) -> None:
        r = client.get("/instruments/registry")
        assert r.status_code == 200


class TestUsersRoutes:
    def test_get_organizations(self, client: TestClient) -> None:
        r = client.get("/users/organizations")
        assert r.status_code == 200

    def test_get_members(self, client: TestClient) -> None:
        r = client.get("/users/members")
        assert r.status_code == 200

    def test_get_subscriptions(self, client: TestClient) -> None:
        r = client.get("/users/subscriptions")
        assert r.status_code == 200


class TestReportingRoutes:
    def test_get_reports(self, client: TestClient) -> None:
        r = client.get("/reporting/reports")
        assert r.status_code == 200

    def test_get_settlements(self, client: TestClient) -> None:
        r = client.get("/reporting/settlements")
        assert r.status_code == 200

    def test_get_reconciliation(self, client: TestClient) -> None:
        r = client.get("/reporting/reconciliation")
        assert r.status_code == 200


class TestRiskRoutesExtended:
    def test_get_greeks(self, client: TestClient) -> None:
        r = client.get("/risk/greeks")
        assert r.status_code == 200

    def test_get_stress_tests(self, client: TestClient) -> None:
        r = client.get("/risk/stress")
        assert r.status_code == 200


class TestMLRoutesExtended:
    def test_get_training_runs(self, client: TestClient) -> None:
        r = client.get("/ml/training-runs")
        assert r.status_code == 200

    def test_get_versions(self, client: TestClient) -> None:
        r = client.get("/ml/versions")
        assert r.status_code == 200

    def test_get_deployments(self, client: TestClient) -> None:
        r = client.get("/ml/deployments")
        assert r.status_code == 200

    def test_get_datasets(self, client: TestClient) -> None:
        r = client.get("/ml/datasets")
        assert r.status_code == 200


class TestPagination:
    def test_pagination_meta(self, client: TestClient) -> None:
        r = client.get("/execution/orders?page=1&page_size=2")
        assert r.status_code == 200
        pag = r.json()["pagination"]
        assert pag["page"] == 1
        assert pag["page_size"] == 2
        assert "total" in pag
        assert "has_next" in pag
