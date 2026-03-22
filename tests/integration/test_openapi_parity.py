"""OpenAPI schema parity — verify all routes are documented and responses match."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from unified_trading_library.core.mock_state_store import MockStateStore

    from unified_trading_api.main import create_app
    from unified_trading_api.mock_data.seed import seed_all_domains
    from unified_trading_api.services.mock_service import MockDomainService

    app = create_app()
    app.state.mock_mode = True
    app.state.disable_auth = True
    app.state.start_time = 0.0
    store = MockStateStore("test-openapi")
    seed_all_domains(store)
    app.state.service = MockDomainService(store)
    app.state.mock_store = store
    return TestClient(app)


class TestOpenAPISpec:
    def test_openapi_endpoint_returns_json(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert "paths" in spec
        assert "info" in spec

    def test_all_registered_paths_in_spec(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        spec = r.json()
        paths = set(spec["paths"].keys())

        required_paths = [
            "/execution/orders",
            "/execution/fills",
            "/positions/active",
            "/analytics/pnl",
            "/ml/model-families",
            "/alerts/list",
            "/risk/limits",
            "/service-status/health",
            "/admin/reset",
            "/health",
        ]

        for path in required_paths:
            assert path in paths, f"Missing path in OpenAPI spec: {path}"

    def test_spec_has_response_schemas(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        spec = r.json()
        # At least some paths should have response schemas
        orders_path = spec["paths"].get("/execution/orders", {})
        get_op = orders_path.get("get", {})
        assert "responses" in get_op
        assert "200" in get_op["responses"]


class TestResponseSchemaMatch:
    """Verify actual responses match expected structure."""

    def test_orders_response_has_data_and_pagination(self, client: TestClient) -> None:
        r = client.get("/execution/orders")
        body = r.json()
        assert "data" in body
        assert "pagination" in body
        assert isinstance(body["data"], list)
        pag = body["pagination"]
        assert "total" in pag
        assert "page" in pag
        assert "page_size" in pag
        assert "has_next" in pag

    def test_order_record_has_required_fields(self, client: TestClient) -> None:
        r = client.get("/execution/orders")
        orders = r.json()["data"]
        if orders:
            order = orders[0]
            for field in ["order_id", "venue", "instrument", "side", "status", "org_id"]:
                assert field in order, f"Order missing field: {field}"

    def test_position_record_has_required_fields(self, client: TestClient) -> None:
        r = client.get("/positions/active")
        data = r.json()
        positions = data.get("data", data.get("positions", []))
        if positions:
            pos = positions[0]
            for field in ["instrument", "venue", "side", "org_id"]:
                assert field in pos, f"Position missing field: {field}"

    def test_alert_record_has_required_fields(self, client: TestClient) -> None:
        r = client.get("/alerts/list")
        alerts = r.json()["data"]
        if alerts:
            alert = alerts[0]
            for field in ["alert_id", "severity", "message", "org_id"]:
                assert field in alert, f"Alert missing field: {field}"

    def test_service_health_record_has_required_fields(self, client: TestClient) -> None:
        r = client.get("/service-status/health")
        data = r.json()
        services = data.get("data", data.get("services", []))
        if services:
            svc = services[0]
            for field in ["service", "status"]:
                assert field in svc, f"Service health missing field: {field}"
