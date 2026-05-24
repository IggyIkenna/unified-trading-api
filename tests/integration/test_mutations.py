"""Verify POST/PUT/DELETE route behavior works correctly."""

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
    store = MockStateStore("test-mutations")
    seed_all_domains(store)
    app.state.service = MockDomainService(store)
    app.state.mock_store = store
    return TestClient(app)


class TestExecutionMutations:
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
        body = r.json()
        assert "data" in body
        inner = body["data"]
        assert inner["status"] == "filled"
        assert inner["order"]["venue"] == "binance"

    def test_created_order_appears_in_list(self, client: TestClient) -> None:
        # Create
        client.post(
            "/execution/orders",
            json={"venue": "test-venue", "instrument": "TEST-USDT", "side": "buy"},
        )
        # List
        r = client.get("/execution/orders?venue=test-venue")
        assert r.status_code == 200
        found = [o for o in r.json()["data"] if o.get("venue") == "test-venue"]
        assert len(found) > 0


class TestOrgScoping:
    """Verify org-scoped filtering works via X-Demo-Persona header."""

    def test_admin_sees_all_data(self, client: TestClient) -> None:
        r = client.get(
            "/execution/orders",
            headers={"X-Demo-Persona": "admin"},
        )
        assert r.status_code == 200
        orgs = {str(o.get("org_id")) for o in r.json()["data"]}
        assert len(orgs) > 1  # admin sees multiple orgs

    def test_client_sees_only_own_org(self, client: TestClient) -> None:
        r = client.get(
            "/execution/orders",
            headers={"X-Demo-Persona": "client-full"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        for order in data:
            assert order.get("org_id") == "acme", f"Client-full should only see acme data, got {order.get('org_id')}"

    def test_data_only_client_sees_own_org(self, client: TestClient) -> None:
        r = client.get(
            "/execution/orders",
            headers={"X-Demo-Persona": "client-data-only"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        for order in data:
            assert order.get("org_id") == "beta"


class TestAdminReset:
    def test_reset_clears_mutations(self, client: TestClient) -> None:
        # Create
        client.post(
            "/execution/orders",
            json={"venue": "reset-test", "instrument": "X"},
        )
        # Reset
        r = client.post("/admin/reset")
        assert r.status_code == 200
        # Verify gone
        r2 = client.get("/execution/orders?venue=reset-test")
        assert len(r2.json()["data"]) == 0

    def test_reset_preserves_seed(self, client: TestClient) -> None:
        client.post("/admin/reset")
        r = client.get("/execution/orders")
        assert len(r.json()["data"]) > 0
