"""Tests for DeFi LP routes — position range, impermanent loss, rebalance, ML confidence, fees."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService


class TestDefiLpPositionRange:
    def test_get_position_range_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "defi_lp_position_range",
            [
                {
                    "pool": "ETH/USDC",
                    "venue_id": "UNISWAP_V3-ETHEREUM",
                    "current_tick": 200500,
                    "tick_lower": 195000,
                    "tick_upper": 205000,
                    "position_value_usd": 250000,
                    "near_edge_warning": False,
                }
            ],
        )
        resp = app_client.get("/defi/lp/position-range")
        assert resp.status_code == 200

    def test_get_position_range_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "defi_lp_position_range",
            [{"pool": "ETH/USDC", "venue_id": "UNISWAP_V3-ETHEREUM"}],
        )
        resp = app_client.get("/defi/lp/position-range")
        data = resp.json()
        assert "data" in data
        assert "mode" in data

    def test_get_position_range_fallback_when_empty(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        """When no seed data, endpoint returns fallback mock data."""
        mock_service.seed("defi_lp_position_range", [])
        resp = app_client.get("/defi/lp/position-range")
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["pool"] == "ETH/USDC"
        assert "current_price" in result
        assert "range_utilization" in result


class TestDefiLpImpermanentLoss:
    def test_get_impermanent_loss_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "defi_lp_impermanent_loss",
            [{"timestamp": "2026-04-10", "il_pct": -0.42, "lp_value_usd": 248_000}],
        )
        resp = app_client.get("/defi/lp/impermanent-loss")
        assert resp.status_code == 200

    def test_get_impermanent_loss_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("defi_lp_impermanent_loss", [{"timestamp": "2026-04-10"}])
        resp = app_client.get("/defi/lp/impermanent-loss")
        data = resp.json()
        assert "data" in data
        assert "mode" in data


class TestDefiLpRebalanceHistory:
    def test_get_rebalance_history_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "defi_lp_rebalance_history",
            [
                {
                    "timestamp": "2026-04-10T14:00:00Z",
                    "old_tick_lower": 190000,
                    "new_tick_lower": 195000,
                    "gas_usd": 12.50,
                }
            ],
        )
        resp = app_client.get("/defi/lp/rebalance-history")
        assert resp.status_code == 200


class TestDefiLpMlConfidence:
    def test_get_ml_confidence_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "defi_lp_ml_confidence",
            [
                {
                    "recommended_action": "REBALANCE",
                    "confidence": 0.82,
                    "hold_threshold": 0.65,
                    "model_version": "lp-rebal-v2.3.1",
                }
            ],
        )
        resp = app_client.get("/defi/lp/ml-confidence")
        assert resp.status_code == 200

    def test_get_ml_confidence_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "defi_lp_ml_confidence",
            [{"recommended_action": "HOLD", "confidence": 0.43}],
        )
        resp = app_client.get("/defi/lp/ml-confidence")
        result = resp.json()["data"]
        assert "recommended_action" in result
        assert "confidence" in result

    def test_get_ml_confidence_fallback_when_empty(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("defi_lp_ml_confidence", [])
        resp = app_client.get("/defi/lp/ml-confidence")
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["recommended_action"] == "HOLD"
        assert "top_features" in result
        assert len(result["top_features"]) == 5


class TestDefiLpFeeRevenue:
    def test_get_fee_revenue_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "defi_lp_fee_revenue",
            [{"fees_24h_usd": 142.50, "fees_7d_usd": 987.30, "fee_apr_7d": 20.6}],
        )
        resp = app_client.get("/defi/lp/fee-revenue")
        assert resp.status_code == 200

    def test_get_fee_revenue_fallback_when_empty(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("defi_lp_fee_revenue", [])
        resp = app_client.get("/defi/lp/fee-revenue")
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["fees_24h_usd"] == 142.50
        assert result["token0_symbol"] == "ETH"
        assert result["token1_symbol"] == "USDC"
