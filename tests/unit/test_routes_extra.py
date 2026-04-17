"""Tests for route modules (continued) — reporting, ML, config, audit, deployment,
documents, derivatives, compliance, service-status, users, admin.

Split from test_routes.py to keep files under 900 lines.
Uses the app_client fixture from conftest.py which provides a TestClient
with mock mode + auth disabled + an in-memory service.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService

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
        assert resp.json()["data"]["status"] == "ready"

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
        assert resp.json()["data"]["status"] == "created"

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
        assert resp.json()["data"] == {}

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
        assert resp.json()["data"]["status"] == "created"

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
        assert resp.json()["data"]["status"] == "promoted"

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
        assert resp.json()["data"] == {}

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
        assert "upload_url" in resp.json()["data"]

    def test_get_download_url_found(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("documents", [{"id": "doc1", "name": "report.pdf"}])
        resp = app_client.get("/documents/download-url?document_id=doc1")
        assert resp.status_code == 200
        assert "download_url" in resp.json()["data"]

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
        assert resp.json()["data"]["status"] == "deleted"

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
        greeks = resp.json()["data"]
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
        data = resp.json()["data"]
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
        from tests.unit.conftest import InMemoryService as _InMemoryService
        from unified_trading_api.main import create_app

        app = create_app()
        svc = _InMemoryService()
        app.state.mock_mode = False
        app.state.disable_auth = True
        app.state.start_time = 0.0
        app.state.service = svc
        client = TestClient(app)
        resp = client.post("/admin/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "forbidden"
