"""Tests for Events routes — calendar, predictions, news, positions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService


class TestEventsCalendar:
    def test_get_calendar_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_calendar",
            [
                {
                    "id": "ev-1",
                    "name": "FOMC Rate Decision",
                    "event_type": "FOMC",
                    "scheduled_at": "2026-04-20T18:00:00Z",
                    "impact": "HIGH",
                    "previous_value": "4.50%",
                    "forecast": "4.25%",
                    "region": "US",
                },
            ],
        )
        resp = app_client.get("/events/calendar")
        assert resp.status_code == 200

    def test_get_calendar_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("events_calendar", [{"id": "ev-1", "impact": "HIGH", "region": "US"}])
        resp = app_client.get("/events/calendar")
        data = resp.json()
        assert "data" in data
        assert "count" in data

    def test_get_calendar_filter_by_impact(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_calendar",
            [
                {"id": "ev-1", "impact": "HIGH", "region": "US"},
                {"id": "ev-2", "impact": "LOW", "region": "US"},
            ],
        )
        resp = app_client.get("/events/calendar?impact=HIGH")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(str(r.get("impact", "")).upper() == "HIGH" for r in records)

    def test_get_calendar_filter_by_region(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_calendar",
            [
                {"id": "ev-1", "impact": "HIGH", "region": "US"},
                {"id": "ev-2", "impact": "HIGH", "region": "EU"},
            ],
        )
        resp = app_client.get("/events/calendar?region=EU")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(str(r.get("region", "")).upper() == "EU" for r in records)


class TestEventsPredictions:
    def test_get_predictions_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_predictions",
            [
                {
                    "id": "pred-1",
                    "event_id": "ev-1",
                    "event_name": "FOMC",
                    "instrument": "BTC-USD",
                    "confidence": 0.78,
                },
            ],
        )
        resp = app_client.get("/events/predictions")
        assert resp.status_code == 200

    def test_get_predictions_filter_by_event_id(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_predictions",
            [
                {"id": "pred-1", "event_id": "ev-1", "instrument": "BTC-USD"},
                {"id": "pred-2", "event_id": "ev-2", "instrument": "ETH-USD"},
            ],
        )
        resp = app_client.get("/events/predictions?event_id=ev-1")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(r["event_id"] == "ev-1" for r in records)

    def test_get_predictions_filter_by_instrument(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_predictions",
            [
                {"id": "pred-1", "event_id": "ev-1", "instrument": "BTC-USD"},
                {"id": "pred-2", "event_id": "ev-1", "instrument": "ETH-USD"},
            ],
        )
        resp = app_client.get("/events/predictions?instrument=BTC-USD")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(str(r["instrument"]).upper() == "BTC-USD" for r in records)


class TestEventsNews:
    def test_get_news_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_news",
            [
                {
                    "id": "news-1",
                    "title": "Fed Holds Rates Steady",
                    "source": "Reuters",
                    "published_at": "2026-04-15T14:00:00Z",
                    "sentiment": "neutral",
                    "category": "macro",
                },
            ],
        )
        resp = app_client.get("/events/news")
        assert resp.status_code == 200

    def test_get_news_filter_by_sentiment(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_news",
            [
                {"id": "news-1", "sentiment": "bullish", "category": "macro"},
                {"id": "news-2", "sentiment": "bearish", "category": "macro"},
            ],
        )
        resp = app_client.get("/events/news?sentiment=bullish")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(str(r.get("sentiment", "")).lower() == "bullish" for r in records)

    def test_get_news_filter_by_category(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_news",
            [
                {"id": "news-1", "sentiment": "neutral", "category": "macro"},
                {"id": "news-2", "sentiment": "neutral", "category": "on-chain"},
            ],
        )
        resp = app_client.get("/events/news?category=macro")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(str(r.get("category", "")).lower() == "macro" for r in records)

    def test_get_news_respects_limit(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_news",
            [{"id": f"news-{i}", "sentiment": "neutral", "category": "macro"} for i in range(10)],
        )
        resp = app_client.get("/events/news?limit=3")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert len(records) <= 3


class TestEventsPositions:
    def test_get_positions_returns_200(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_positions",
            [
                {
                    "id": "epos-1",
                    "event_id": "ev-1",
                    "event_name": "FOMC",
                    "instrument": "BTC-USD",
                    "direction": "LONG",
                    "entry_price": 65000,
                    "current_price": 66200,
                    "size": 1.5,
                    "pnl_usd": 1800,
                    "phase": "PRE_EVENT",
                },
            ],
        )
        resp = app_client.get("/events/positions")
        assert resp.status_code == 200

    def test_get_positions_filter_by_phase(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_positions",
            [
                {"id": "epos-1", "phase": "PRE_EVENT", "event_id": "ev-1"},
                {"id": "epos-2", "phase": "POST_EVENT", "event_id": "ev-1"},
            ],
        )
        resp = app_client.get("/events/positions?phase=PRE_EVENT")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(str(r.get("phase", "")).upper() == "PRE_EVENT" for r in records)

    def test_get_positions_filter_by_event_id(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "events_positions",
            [
                {"id": "epos-1", "phase": "PRE_EVENT", "event_id": "ev-1"},
                {"id": "epos-2", "phase": "PRE_EVENT", "event_id": "ev-2"},
            ],
        )
        resp = app_client.get("/events/positions?event_id=ev-1")
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert all(r["event_id"] == "ev-1" for r in records)

    def test_get_positions_response_shape(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed("events_positions", [{"id": "epos-1", "event_id": "ev-1"}])
        resp = app_client.get("/events/positions")
        data = resp.json()
        assert "data" in data
        assert "count" in data
