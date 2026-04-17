"""Tests for DeFi Lending routes — protocol APY comparison, arb positions, rate impact."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestDefiLendingRates:
    def test_get_rates_returns_200(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/rates")
        assert resp.status_code == 200

    def test_get_rates_response_shape(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/rates")
        data = resp.json()
        assert "data" in data
        assert "pagination" in data
        assert "mode" in data

    def test_get_rates_contains_seed_protocols(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/rates")
        data = resp.json()
        protocols = {str(r["protocol"]) for r in data["data"]}
        assert "Aave V3" in protocols
        assert "Morpho Blue" in protocols
        assert "Compound V3" in protocols

    def test_get_rates_record_fields(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/rates")
        data = resp.json()
        assert len(data["data"]) > 0
        record = data["data"][0]
        assert "protocol" in record
        assert "token" in record
        assert "supply_apy_pct" in record
        assert "borrow_apy_pct" in record
        assert "spread_bps" in record
        assert "utilization_pct" in record
        assert "tvl_usd" in record

    def test_get_rates_pagination(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/rates")
        pagination = resp.json()["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 50
        assert isinstance(pagination["total"], int)
        assert isinstance(pagination["has_next"], bool)


class TestDefiLendingPositions:
    def test_get_positions_returns_200(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/positions")
        assert resp.status_code == 200

    def test_get_positions_response_shape(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/positions")
        data = resp.json()
        assert "data" in data
        assert "pagination" in data

    def test_get_positions_record_fields(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/positions")
        data = resp.json()
        assert len(data["data"]) > 0
        record = data["data"][0]
        assert "id" in record
        assert "borrow_protocol" in record
        assert "lend_protocol" in record
        assert "token" in record
        assert "notional_usd" in record
        assert "health_factor" in record
        assert "status" in record

    def test_get_positions_contains_seed_data(self, app_client: TestClient) -> None:
        resp = app_client.get("/defi/lending/positions")
        data = resp.json()
        ids = {str(r["id"]) for r in data["data"]}
        assert "pos-la-001" in ids


class TestDefiLendingSimulateRateImpact:
    def test_simulate_rate_impact_returns_200(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/defi/lending/simulate-rate-impact",
            json={"protocol": "Aave V3", "token": "USDC", "amount_usd": 1_000_000},
        )
        assert resp.status_code == 200

    def test_simulate_rate_impact_response_shape(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/defi/lending/simulate-rate-impact",
            json={"protocol": "Aave V3", "token": "USDC", "amount_usd": 1_000_000},
        )
        data = resp.json()
        assert "data" in data
        result = data["data"]
        assert "protocol" in result
        assert "token" in result
        assert "current_supply_apy_pct" in result
        assert "projected_supply_apy_pct" in result
        assert "current_borrow_apy_pct" in result
        assert "projected_borrow_apy_pct" in result
        assert "rate_delta_supply_bps" in result
        assert "rate_delta_borrow_bps" in result

    def test_simulate_rate_impact_larger_amount_has_bigger_impact(
        self, app_client: TestClient
    ) -> None:
        small = app_client.post(
            "/defi/lending/simulate-rate-impact",
            json={"protocol": "Aave V3", "token": "USDC", "amount_usd": 100_000},
        ).json()["data"]
        large = app_client.post(
            "/defi/lending/simulate-rate-impact",
            json={"protocol": "Aave V3", "token": "USDC", "amount_usd": 1_000_000_000},
        ).json()["data"]
        # Larger amount should compress supply APY more
        assert large["projected_supply_apy_pct"] < small["projected_supply_apy_pct"]

    def test_simulate_rate_impact_unknown_protocol(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/defi/lending/simulate-rate-impact",
            json={"protocol": "Unknown", "token": "USDC", "amount_usd": 1000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data["data"]

    def test_simulate_rate_impact_invalid_body(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/defi/lending/simulate-rate-impact",
            json={"protocol": "Aave V3"},
        )
        assert resp.status_code == 422
