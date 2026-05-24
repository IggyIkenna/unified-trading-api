"""Tests for DeFi Basis Trade routes — funding matrix, LST collateral, venue allocation, directions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService


class TestDefiBasisFundingMatrix:
    def test_get_funding_matrix_returns_200(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "basis_funding_matrix",
            [{"ETH": {"BINANCE": 0.01, "BYBIT": 0.012}, "BTC": {"BINANCE": 0.008}}],
        )
        resp = app_client.get("/defi/basis/funding-matrix")
        assert resp.status_code == 200

    def test_get_funding_matrix_response_shape(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("basis_funding_matrix", [{"ETH": {"BINANCE": 0.01}}])
        resp = app_client.get("/defi/basis/funding-matrix")
        data = resp.json()
        assert "data" in data
        assert "mode" in data

    def test_get_funding_matrix_empty(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("basis_funding_matrix", [])
        resp = app_client.get("/defi/basis/funding-matrix")
        assert resp.status_code == 200
        # When no records, matrix should be empty dict
        assert resp.json()["data"] == {}


class TestDefiBasisLstCollateral:
    def test_get_lst_collateral_returns_200(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "basis_lst_collateral",
            [{"token": "wstETH", "utilization_pct": 85.2, "position_usd": 5_000_000}],
        )
        resp = app_client.get("/defi/basis/lst-collateral")
        assert resp.status_code == 200

    def test_get_lst_collateral_response_shape(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("basis_lst_collateral", [{"token": "wstETH"}])
        resp = app_client.get("/defi/basis/lst-collateral")
        data = resp.json()
        assert "data" in data
        assert "mode" in data


class TestDefiBasisVenueAllocation:
    def test_get_venue_allocation_returns_200(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "basis_venue_allocation",
            [{"venue": "BINANCE", "allocation_pct": 45.0, "capital_usd": 12_000_000}],
        )
        resp = app_client.get("/defi/basis/venue-allocation")
        assert resp.status_code == 200

    def test_get_venue_allocation_response_shape(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("basis_venue_allocation", [{"venue": "BINANCE"}])
        resp = app_client.get("/defi/basis/venue-allocation")
        data = resp.json()
        assert "data" in data
        assert "mode" in data


class TestDefiBasisDirections:
    def test_get_directions_returns_200(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "basis_directions",
            [{"coin": "ETH", "direction": "STANDARD", "funding_sign": "positive"}],
        )
        resp = app_client.get("/defi/basis/directions")
        assert resp.status_code == 200

    def test_get_directions_response_shape(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("basis_directions", [{"coin": "ETH"}])
        resp = app_client.get("/defi/basis/directions")
        data = resp.json()
        assert "data" in data
        assert "mode" in data
