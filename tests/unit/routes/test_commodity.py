"""Tests for Commodity regime routes — regime state, factors, COT positioning, history, positions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService


class TestCommodityRegimeState:
    def test_get_regime_state_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_regime_state",
            [
                {
                    "regime": "TRENDING",
                    "confidence": 0.87,
                    "updatedAt": "2026-04-15T10:00:00Z",
                    "priorRegime": "MEAN_REVERTING",
                    "transitionTimestamp": "2026-04-12T08:00:00Z",
                    "hmm_log_likelihood": -142.5,
                }
            ],
        )
        resp = app_client.get("/commodity/regime-state")
        assert resp.status_code == 200

    def test_get_regime_state_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_regime_state",
            [{"regime": "TRENDING", "confidence": 0.87}],
        )
        resp = app_client.get("/commodity/regime-state")
        data = resp.json()
        assert "data" in data
        assert "mode" in data
        result = data["data"]
        assert "regime" in result
        assert "confidence" in result

    def test_get_regime_state_fallback_when_empty(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("commodity_regime_state", [])
        resp = app_client.get("/commodity/regime-state")
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["regime"] == "UNKNOWN"
        assert result["confidence"] == 0.0


class TestCommodityFactors:
    def test_get_factors_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_factors",
            [
                {"name": "Rig Count", "score": 0.72, "signal": "BULLISH", "weight": 20},
                {"name": "COT Positioning", "score": 0.45, "signal": "BULLISH", "weight": 25},
            ],
        )
        resp = app_client.get("/commodity/factors")
        assert resp.status_code == 200

    def test_get_factors_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("commodity_factors", [{"name": "Rig Count"}])
        resp = app_client.get("/commodity/factors")
        data = resp.json()
        assert "data" in data
        assert "mode" in data

    def test_get_factors_returns_list(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_factors",
            [
                {"name": "Rig Count", "score": 0.72},
                {"name": "COT Positioning", "score": 0.45},
                {"name": "Storage Levels", "score": -0.31},
            ],
        )
        resp = app_client.get("/commodity/factors")
        records = resp.json()["data"]
        assert isinstance(records, list)
        assert len(records) == 3


class TestCommodityCotPositioning:
    def test_get_cot_positioning_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_cot_positioning",
            [
                {
                    "date": "2026-04-08",
                    "speculative_net": 125_000,
                    "commercial_net": -98_000,
                    "small_trader_net": -27_000,
                }
            ],
        )
        resp = app_client.get("/commodity/cot-positioning")
        assert resp.status_code == 200

    def test_get_cot_positioning_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("commodity_cot_positioning", [{"date": "2026-04-08"}])
        resp = app_client.get("/commodity/cot-positioning")
        data = resp.json()
        assert "data" in data
        assert "mode" in data


class TestCommodityRegimeHistory:
    def test_get_regime_history_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_regime_history",
            [
                {
                    "date": "2026-04-01",
                    "regime": "TRENDING",
                    "confidence": 0.82,
                    "transition": True,
                }
            ],
        )
        resp = app_client.get("/commodity/regime-history")
        assert resp.status_code == 200


class TestCommodityPositions:
    def test_get_positions_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_positions",
            [
                {
                    "commodity": "WTI Crude",
                    "direction": "LONG",
                    "entry": 72.4,
                    "current": 78.2,
                    "pnl": 58000,
                    "regime_at_entry": "TRENDING",
                }
            ],
        )
        resp = app_client.get("/commodity/positions")
        assert resp.status_code == 200

    def test_get_positions_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "commodity_positions",
            [{"commodity": "WTI Crude", "direction": "LONG"}],
        )
        resp = app_client.get("/commodity/positions")
        data = resp.json()
        assert "data" in data
        assert "mode" in data
