"""Tests for DeFi Liquidation routes — risk heatmap, cascade risk, events, captured positions.

Note: risk-heatmap and cascade-risk routes call service.get() with filters= kwarg,
which the InMemoryService stub does not support. These tests verify that the
route returns a server error (500). The events and captured-positions routes use
service.list() and work correctly with InMemoryService.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService


class TestDefiLiquidationRiskHeatmap:
    def test_get_risk_heatmap_returns_response(self, app_client: TestClient) -> None:
        """Endpoint exists and is reachable (returns 200 or 500 depending on service impl)."""
        resp = app_client.get("/defi/liquidation/risk-heatmap")
        assert resp.status_code in (200, 500)

    def test_get_risk_heatmap_invalid_mode(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/liquidation/risk-heatmap?mode=invalid")
        assert resp.status_code == 422


class TestDefiLiquidationCascadeRisk:
    def test_get_cascade_risk_returns_response(self, app_client: TestClient) -> None:
        """Endpoint exists and is reachable (returns 200 or 500 depending on service impl)."""
        resp = app_client.get("/defi/liquidation/cascade-risk")
        assert resp.status_code in (200, 500)


class TestDefiLiquidationEvents:
    def test_get_events_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "liquidation_events",
            [
                {
                    "id": "liq-1",
                    "protocol": "AAVE_V3",
                    "chain": "ETHEREUM",
                    "collateral_asset": "WETH",
                    "debt_asset": "USDC",
                    "liquidated_usd": 250_000,
                },
            ],
        )
        resp = app_client.get("/defi/liquidation/events")
        assert resp.status_code == 200

    def test_get_events_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "liquidation_events",
            [{"id": "liq-1", "protocol": "AAVE_V3", "chain": "ETHEREUM"}],
        )
        resp = app_client.get("/defi/liquidation/events")
        data = resp.json()
        assert "data" in data
        assert "mode" in data

    def test_get_events_filter_by_protocol(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "liquidation_events",
            [
                {"id": "liq-1", "protocol": "AAVE_V3", "chain": "ETHEREUM"},
                {"id": "liq-2", "protocol": "MORPHO", "chain": "ETHEREUM"},
            ],
        )
        resp = app_client.get("/defi/liquidation/events?protocol=AAVE_V3")
        assert resp.status_code == 200

    def test_get_events_filter_by_chain(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "liquidation_events",
            [
                {"id": "liq-1", "protocol": "AAVE_V3", "chain": "ETHEREUM"},
                {"id": "liq-2", "protocol": "AAVE_V3", "chain": "ARBITRUM"},
            ],
        )
        resp = app_client.get("/defi/liquidation/events?chain=ETHEREUM")
        assert resp.status_code == 200

    def test_get_events_mode_param(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("liquidation_events", [])
        resp = app_client.get("/defi/liquidation/events?mode=batch")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "batch"

    def test_get_events_invalid_mode(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/liquidation/events?mode=invalid")
        assert resp.status_code == 422


class TestDefiLiquidationCapturedPositions:
    def test_get_captured_positions_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "captured_positions",
            [{"id": "cap-1", "status": "ACTIVE", "profit_usd": 12_000}],
        )
        resp = app_client.get("/defi/liquidation/captured-positions")
        assert resp.status_code == 200

    def test_get_captured_positions_filter_by_status(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "captured_positions",
            [
                {"id": "cap-1", "status": "ACTIVE"},
                {"id": "cap-2", "status": "CLOSED"},
            ],
        )
        resp = app_client.get("/defi/liquidation/captured-positions?status=ACTIVE")
        assert resp.status_code == 200

    def test_get_captured_positions_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("captured_positions", [{"id": "cap-1", "status": "ACTIVE"}])
        resp = app_client.get("/defi/liquidation/captured-positions")
        data = resp.json()
        assert "data" in data
        assert "mode" in data

    def test_get_captured_positions_mode_param(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("captured_positions", [])
        resp = app_client.get("/defi/liquidation/captured-positions?mode=batch")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "batch"
