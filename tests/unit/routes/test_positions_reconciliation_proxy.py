"""Tests for the strategy-service/position reconciliation-API gateway proxy
in positions.py.

Covers:
  * GET /positions/reconciliation/deviations — mock mode (MockStateStore) +
    real-mode proxy (forwards status param + status code)
  * GET /positions/reconciliation/balances — mock mode + real-mode proxy
  * GET /positions/reconciliation/pnl — mock mode + real-mode proxy
  * GET /positions/reconciliation/summary — mock mode (computed from
    recon_deviations) + real-mode proxy
  * POST /positions/reconciliation/resolve — mock mode (honest ack) +
    real-mode proxy (forwards body + status code)
  * GET /positions/reconciliation/auto-recon/history — mock mode + real-mode
    proxy
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService
from unified_trading_api.routes import positions


class _FakeAsyncClient:
    """Minimal async context-manager stand-in for httpx.AsyncClient.

    Captures the (method, path, params, json) of the single request it
    handles and returns a caller-supplied canned httpx.Response — mirrors
    the pattern in test_reporting_blrs_proxy.py, since positions.py builds
    its own AsyncClient internally (no injectable client seam).
    """

    last_call: dict[str, object] | None = None

    def __init__(self, *, base_url: str, timeout: float) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        _FakeAsyncClient.last_call = {
            "method": method,
            "path": path,
            "base_url": self.base_url,
            "params": params,
            "json": json,
        }
        return _canned_response


_canned_response: httpx.Response = httpx.Response(200, json={})


def _set_canned_response(resp: httpx.Response) -> None:
    global _canned_response
    _canned_response = resp


@pytest.fixture(autouse=True)
def _reset_canned_response() -> None:
    _set_canned_response(httpx.Response(200, json={}))
    _FakeAsyncClient.last_call = None


class TestReconciliationDeviationsMockMode:
    def test_get_deviations_empty_when_unseeded(self, app_client: TestClient) -> None:
        resp = app_client.get("/positions/reconciliation/deviations")
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_get_deviations_filters_by_uppercased_status(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "recon_deviations",
            [
                {"deviation_id": "DEV-1", "status": "TRANSIENT"},
                {"deviation_id": "DEV-2", "status": "CONFIRMED"},
            ],
        )
        resp = app_client.get("/positions/reconciliation/deviations", params={"status": "transient"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"deviation_id": "DEV-1", "status": "TRANSIENT"}]


class TestReconciliationBalancesMockMode:
    def test_get_balances_empty_when_unseeded(self, app_client: TestClient) -> None:
        resp = app_client.get("/positions/reconciliation/balances")
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_get_balances_filters_by_venue(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "recon_balances",
            [{"venue": "Binance", "asset": "USDT"}, {"venue": "OKX", "asset": "USDT"}],
        )
        resp = app_client.get("/positions/reconciliation/balances", params={"venue": "Binance"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"venue": "Binance", "asset": "USDT"}]


class TestReconciliationPnlMockMode:
    def test_get_pnl_empty_when_unseeded(self, app_client: TestClient) -> None:
        resp = app_client.get("/positions/reconciliation/pnl")
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_get_pnl_filters_by_venue(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("recon_pnl", [{"venue": "Bybit", "pnl": 12.5}])
        resp = app_client.get("/positions/reconciliation/pnl", params={"venue": "Bybit"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"venue": "Bybit", "pnl": 12.5}]


class TestReconciliationSummaryMockMode:
    def test_summary_zero_state_when_unseeded(self, app_client: TestClient) -> None:
        resp = app_client.get("/positions/reconciliation/summary")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "total_deviations": 0,
            "transient": 0,
            "confirmed": 0,
            "auto_reconciled": 0,
            "escalated": 0,
            "resolved": 0,
            "last_run": None,
        }

    def test_summary_computed_from_seeded_deviations(
        self, app_client: TestClient, mock_service: InMemoryService
    ) -> None:
        mock_service.seed(
            "recon_deviations",
            [
                {"deviation_id": "DEV-1", "status": "TRANSIENT"},
                {"deviation_id": "DEV-2", "status": "CONFIRMED"},
                {"deviation_id": "DEV-3", "status": "RESOLVED"},
            ],
        )
        resp = app_client.get("/positions/reconciliation/summary")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_deviations"] == 3
        assert data["transient"] == 1
        assert data["confirmed"] == 1
        assert data["resolved"] == 1
        assert data["last_run"] is None


class TestReconciliationResolveMockMode:
    def test_resolve_deviation_mock_mode_acknowledges(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/positions/reconciliation/resolve",
            json={
                "deviation_id": "DEV-1",
                "action": "accept",
                "note": "expected timing divergence",
                "resolved_by": "operator@example.com",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["deviation_id"] == "DEV-1"
        assert data["action"] == "accept"
        assert data["status"] == "resolved"

    def test_resolve_deviation_investigate_status(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/positions/reconciliation/resolve",
            json={
                "deviation_id": "DEV-2",
                "action": "investigate",
                "note": "needs a closer look",
                "resolved_by": "operator@example.com",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "investigating"

    def test_resolve_deviation_note_too_short_rejected(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/positions/reconciliation/resolve",
            json={
                "deviation_id": "DEV-1",
                "action": "accept",
                "note": "short",
                "resolved_by": "operator@example.com",
            },
        )
        assert resp.status_code == 422


class TestAutoReconHistoryMockMode:
    def test_history_empty_when_unseeded(self, app_client: TestClient) -> None:
        resp = app_client.get("/positions/reconciliation/auto-recon/history")
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_history_returns_seeded_records(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed("recon_auto_history", [{"deviation_id": "DEV-9", "status": "AUTO_RECONCILED"}])
        resp = app_client.get("/positions/reconciliation/auto-recon/history")
        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"deviation_id": "DEV-9", "status": "AUTO_RECONCILED"}]


class TestReconciliationRealModeProxy:
    def test_get_deviations_proxies_and_forwards_params(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.setenv(positions._STRATEGY_SERVICE_URL_ENV, "http://strategy.test")
        monkeypatch.setattr(positions.httpx, "AsyncClient", _FakeAsyncClient)
        _set_canned_response(httpx.Response(200, json=[{"deviation_id": "DEV-9", "status": "TRANSIENT"}]))

        resp = app_client.get("/positions/reconciliation/deviations", params={"status": "transient"})

        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"deviation_id": "DEV-9", "status": "TRANSIENT"}]
        call = _FakeAsyncClient.last_call
        assert call is not None
        assert call["method"] == "GET"
        assert call["path"] == "/reconciliation/deviations"
        assert call["base_url"] == "http://strategy.test"
        assert call["params"] == {"status": "transient"}

    def test_get_summary_proxies_raw(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.setenv(positions._STRATEGY_SERVICE_URL_ENV, "http://strategy.test")
        monkeypatch.setattr(positions.httpx, "AsyncClient", _FakeAsyncClient)
        _set_canned_response(
            httpx.Response(
                200,
                json={
                    "total_deviations": 2,
                    "transient": 1,
                    "confirmed": 0,
                    "auto_reconciled": 0,
                    "escalated": 0,
                    "resolved": 1,
                    "last_run": "2026-07-31T00:00:00+00:00",
                },
            )
        )

        resp = app_client.get("/positions/reconciliation/summary")

        assert resp.status_code == 200, resp.text
        assert resp.json()["total_deviations"] == 2
        call = _FakeAsyncClient.last_call
        assert call is not None
        assert call["path"] == "/reconciliation/summary"

    def test_resolve_deviation_proxies_body_and_forwards_status(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.setenv(positions._STRATEGY_SERVICE_URL_ENV, "http://strategy.test")
        monkeypatch.setattr(positions.httpx, "AsyncClient", _FakeAsyncClient)
        _set_canned_response(
            httpx.Response(
                404,
                json={"detail": "Deviation DEV-404 not found"},
            )
        )

        resp = app_client.post(
            "/positions/reconciliation/resolve",
            json={
                "deviation_id": "DEV-404",
                "action": "accept",
                "note": "expected timing divergence",
                "resolved_by": "operator@example.com",
            },
        )

        # strategy-service's real 404 is forwarded verbatim, not masked as a mock-mode 200.
        assert resp.status_code == 404
        call = _FakeAsyncClient.last_call
        assert call is not None
        assert call["method"] == "POST"
        assert call["path"] == "/reconciliation/resolve"
        assert call["json"] == {
            "deviation_id": "DEV-404",
            "action": "accept",
            "note": "expected timing divergence",
            "resolved_by": "operator@example.com",
        }

    def test_no_strategy_url_configured_falls_back_to_mock(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.delenv(positions._STRATEGY_SERVICE_URL_ENV, raising=False)

        resp = app_client.get("/positions/reconciliation/auto-recon/history")

        assert resp.status_code == 200, resp.text
        assert resp.json() == []


__all__: list[str] = []
