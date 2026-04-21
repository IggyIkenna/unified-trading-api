"""Tests for Registry admin routes — strategy-instance lifecycle PATCH."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService


def _seed_instance(
    mock_service: InMemoryService,
    *,
    instance_id: str = "elysium-base-btc",
    maturity_phase: str = "paper_1d",
    product_routing: str = "dart_only",
) -> None:
    mock_service.seed(
        "strategy_instance_lifecycle",
        [
            {
                "id": instance_id,
                "instance_id": instance_id,
                "maturity_phase": maturity_phase,
                "product_routing": product_routing,
                "available_since": "2026-04-01T00:00:00+00:00",
                "phased_at": "2026-04-14T00:00:00+00:00",
            }
        ],
    )


class TestPatchLifecycleValidation:
    def test_404_when_instance_unknown(self, app_client: TestClient) -> None:
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/unknown/lifecycle",
            json={"maturity_phase": "paper_14d"},
        )
        assert resp.status_code == 404

    def test_400_when_body_empty(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service)
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={},
        )
        assert resp.status_code == 400

    def test_422_when_unknown_maturity_phase(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service)
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"maturity_phase": "bogus_phase"},
        )
        assert resp.status_code == 422

    def test_422_when_extra_fields(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service)
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"maturity_phase": "paper_14d", "hack": 1},
        )
        assert resp.status_code == 422


class TestPatchLifecycleTransitions:
    def test_forward_maturity_transition_succeeds(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service, maturity_phase="paper_1d")
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"maturity_phase": "paper_14d", "rationale": "stabilised"},
        )
        assert resp.status_code == 200
        record = resp.json()["data"]
        assert record["maturity_phase"] == "paper_14d"
        history = record["phase_history"]
        assert len(history) == 1
        assert history[0]["from_phase"] == "paper_1d"
        assert history[0]["to_phase"] == "paper_14d"
        assert history[0]["rationale"] == "stabilised"

    def test_backward_maturity_transition_rejected(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service, maturity_phase="paper_14d")
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"maturity_phase": "paper_1d"},
        )
        assert resp.status_code == 400
        assert "Illegal maturity transition" in resp.json()["detail"]

    def test_retirement_from_any_phase_allowed(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service, maturity_phase="paper_1d")
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"maturity_phase": "retired"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["maturity_phase"] == "retired"

    def test_transition_out_of_retired_rejected(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service, maturity_phase="retired")
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"maturity_phase": "live_early"},
        )
        assert resp.status_code == 400

    def test_product_routing_only_update(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service)
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"product_routing": "both"},
        )
        assert resp.status_code == 200
        record = resp.json()["data"]
        assert record["product_routing"] == "both"
        # Maturity phase untouched; no history row added for a routing-only update.
        assert record["maturity_phase"] == "paper_1d"
        assert "phase_history" not in record or record.get("phase_history") in ([], None)

    def test_combined_phase_plus_routing(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service, maturity_phase="paper_1d", product_routing="dart_only")
        resp = app_client.patch(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
            json={"maturity_phase": "paper_14d", "product_routing": "both"},
        )
        assert resp.status_code == 200
        record = resp.json()["data"]
        assert record["maturity_phase"] == "paper_14d"
        assert record["product_routing"] == "both"


class TestGetLifecycle:
    def test_get_single_returns_record(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        _seed_instance(mock_service, maturity_phase="paper_14d")
        resp = app_client.get(
            "/api/v1/registry/strategy-instances/elysium-base-btc/lifecycle",
        )
        assert resp.status_code == 200
        record = resp.json()["data"]
        assert record["instance_id"] == "elysium-base-btc"
        assert record["maturity_phase"] == "paper_14d"

    def test_get_single_404_when_absent(self, app_client: TestClient) -> None:
        resp = app_client.get(
            "/api/v1/registry/strategy-instances/unknown/lifecycle",
        )
        assert resp.status_code == 404

    def test_list_returns_all_records(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "strategy_instance_lifecycle",
            [
                {"id": "a", "instance_id": "a", "maturity_phase": "paper_1d"},
                {"id": "b", "instance_id": "b", "maturity_phase": "live_early"},
            ],
        )
        resp = app_client.get("/api/v1/registry/strategy-instances/lifecycle")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert isinstance(records, list)
        ids = sorted(r["instance_id"] for r in records)
        assert ids == ["a", "b"]

    def test_list_returns_empty_on_empty_collection(
        self, app_client: TestClient
    ) -> None:
        resp = app_client.get("/api/v1/registry/strategy-instances/lifecycle")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
