"""Integration tests for new endpoints added in Phase 1-8.

Tests: strategies, operational actions, compliance, derivatives,
risk analytics, live/batch mode, reporting, ML training.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from unified_trading_library import MockStateStore

    from unified_trading_api.main import create_app
    from unified_trading_api.mock_data.seed import seed_all_domains
    from unified_trading_api.services.mock_service import MockDomainService

    app = create_app()
    app.state.mock_mode = True
    app.state.disable_auth = True
    app.state.start_time = 0.0
    store = MockStateStore("test-new-endpoints")
    seed_all_domains(store)
    app.state.service = MockDomainService(store)
    app.state.mock_store = store
    return TestClient(app)


class TestStrategyEndpoints:
    def test_get_strategies(self, client: TestClient) -> None:
        r = client.get("/analytics/strategies")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_get_strategy_configs(self, client: TestClient) -> None:
        r = client.get("/analytics/strategy-configs")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_get_strategy_detail_not_found(self, client: TestClient) -> None:
        r = client.get("/analytics/strategies/nonexistent-id")
        assert r.status_code == 200
        assert "error" in r.json()


class TestOperationalActions:
    def test_circuit_breaker_invalid_action(self, client: TestClient) -> None:
        r = client.post(
            "/risk/circuit-breaker",
            json={"strategy_id": "test", "action": "invalid"},
        )
        assert r.status_code == 200
        assert "error" in r.json()

    def test_kill_switch_invalid_scope(self, client: TestClient) -> None:
        r = client.post(
            "/risk/kill-switch",
            json={"scope": "invalid", "target_id": "test"},
        )
        assert r.status_code == 200
        assert "error" in r.json()


class TestRiskAnalytics:
    def test_var_summary(self, client: TestClient) -> None:
        r = client.get("/risk/var-summary")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_stress_test(self, client: TestClient) -> None:
        r = client.get("/risk/stress-test?scenario=GFC_2008")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_correlation_matrix(self, client: TestClient) -> None:
        r = client.get("/risk/correlation-matrix")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_regime(self, client: TestClient) -> None:
        r = client.get("/risk/regime")
        assert r.status_code == 200
        body = r.json()["data"]
        assert "regime" in body or "multiplier" in body

    def test_risk_exposure(self, client: TestClient) -> None:
        r = client.get("/risk/exposure")
        assert r.status_code == 200
        assert "data" in r.json()


class TestComplianceEndpoints:
    def test_pre_trade_check(self, client: TestClient) -> None:
        r = client.post(
            "/compliance/pre-trade-check",
            json={
                "instrument": "BTC-USDT",
                "side": "BUY",
                "quantity": 1,
                "price": 67000,
                "strategy_id": "test-strategy",
            },
        )
        assert r.status_code == 200
        body = r.json()["data"]
        assert "approved" in body
        assert "checks" in body
        assert len(body["checks"]) >= 5


class TestDerivativesEndpoints:
    def test_options_chain(self, client: TestClient) -> None:
        r = client.get("/derivatives/options-chain?underlying=BTC&venue=deribit")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_vol_surface(self, client: TestClient) -> None:
        r = client.get("/derivatives/vol-surface?underlying=BTC")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_portfolio_greeks(self, client: TestClient) -> None:
        r = client.get("/derivatives/portfolio-greeks")
        assert r.status_code == 200
        assert "data" in r.json()


class TestLiveBatchMode:
    def test_positions_live_mode(self, client: TestClient) -> None:
        r = client.get("/positions/active?mode=live")
        assert r.status_code == 200
        assert r.json().get("mode") == "live"

    def test_positions_batch_mode(self, client: TestClient) -> None:
        r = client.get("/positions/active?mode=batch")
        assert r.status_code == 200
        assert r.json().get("mode") == "batch"

    def test_alerts_live_mode(self, client: TestClient) -> None:
        r = client.get("/alerts/list?mode=live")
        assert r.status_code == 200
        assert r.json().get("mode") == "live"

    def test_alerts_batch_mode(self, client: TestClient) -> None:
        r = client.get("/alerts/list?mode=batch")
        assert r.status_code == 200
        assert r.json().get("mode") == "batch"


class TestMarketDataEnhancements:
    def test_fx_rates(self, client: TestClient) -> None:
        r = client.get("/market-data/fx-rates")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_orderbook(self, client: TestClient) -> None:
        r = client.get("/market-data/orderbook?venue=binance&instrument=BTC-USDT")
        assert r.status_code == 200


class TestReportingEnhancements:
    def test_regulatory_reports(self, client: TestClient) -> None:
        r = client.get("/reporting/regulatory")
        assert r.status_code == 200

    def test_generate_report(self, client: TestClient) -> None:
        r = client.post(
            "/reporting/generate",
            json={"type": "pnl", "format": "pdf"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "ready"

    def test_schedules_crud(self, client: TestClient) -> None:
        # Create
        r = client.post(
            "/reporting/schedules",
            json={"frequency": "daily", "report_type": "pnl"},
        )
        assert r.status_code == 200
        # List
        r2 = client.get("/reporting/schedules")
        assert r2.status_code == 200
        assert "data" in r2.json()

    def test_pnl_attribution(self, client: TestClient) -> None:
        r = client.get("/reporting/pnl-attribution")
        assert r.status_code == 200

    def test_executive_summary(self, client: TestClient) -> None:
        r = client.get("/reporting/executive-summary")
        assert r.status_code == 200

    def test_invoices(self, client: TestClient) -> None:
        r = client.get("/reporting/invoices")
        assert r.status_code == 200


class TestMLEnhancements:
    def test_training_jobs(self, client: TestClient) -> None:
        r = client.get("/ml/training-jobs")
        assert r.status_code == 200

    def test_create_training_job(self, client: TestClient) -> None:
        r = client.post(
            "/ml/training-jobs",
            json={"model_family": "test", "config": {}},
        )
        assert r.status_code == 200

    def test_validation_results(self, client: TestClient) -> None:
        r = client.get("/ml/validation-results")
        assert r.status_code == 200


class TestReadinessEndpoint:
    def test_readiness_returns_tier_info(self, client: TestClient) -> None:
        r = client.get("/readiness")
        assert r.status_code == 200
        body = r.json()
        assert "declared_runtime_tier" in body
        assert "effective_runtime_tier" in body
        assert "mock_domain_service" in body
