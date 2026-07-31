"""Tests for the BLRS reconciliation-break gateway proxy in reporting.py.

Covers:
  * GET /reporting/reconciliation/breaks — mock mode (MockStateStore) and
    real mode (proxies to BLRS, forwards query params + status code)
  * POST /reporting/reconciliation/resolve — mock mode + real-mode proxy
  * POST /reporting/reconciliation/book-correction — mock mode (honest
    404, no seeded break to derive booking params from) + real-mode proxy
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryService
from unified_trading_api.routes import reporting


class _FakeAsyncClient:
    """Minimal async context-manager stand-in for httpx.AsyncClient.

    Captures the (method, path, params, json) of the single request it
    handles and returns a caller-supplied canned httpx.Response — mirrors
    the httpx.MockTransport pattern used in test_pbm_performance.py, but
    reporting.py builds its own AsyncClient internally (no injectable
    client seam), so the class itself is monkeypatched instead.
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


class TestReconciliationBreaksMockMode:
    def test_get_breaks_empty_when_unseeded(self, app_client: TestClient) -> None:
        resp = app_client.get("/reporting/reconciliation/breaks")
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_get_breaks_returns_seeded_records(self, app_client: TestClient, mock_service: InMemoryService) -> None:
        mock_service.seed(
            "reconciliation_breaks",
            [{"break_id": "BRK-001", "venue": "Binance", "status": "pending"}],
        )
        resp = app_client.get("/reporting/reconciliation/breaks", params={"venue": "Binance"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"break_id": "BRK-001", "venue": "Binance", "status": "pending"}]

    def test_resolve_break_mock_mode_acknowledges(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/reporting/reconciliation/resolve",
            json={
                "break_id": "BRK-001",
                "action": "accept",
                "note": "expected timing divergence",
                "resolved_by": "operator@example.com",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["break_id"] == "BRK-001"
        assert data["action"] == "accept"
        assert data["status"] == "resolved"

    def test_resolve_break_investigate_status(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/reporting/reconciliation/resolve",
            json={
                "break_id": "BRK-002",
                "action": "investigate",
                "note": "needs a closer look",
                "resolved_by": "operator@example.com",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "investigating"

    def test_resolve_break_note_too_short_rejected(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/reporting/reconciliation/resolve",
            json={
                "break_id": "BRK-001",
                "action": "accept",
                "note": "short",
                "resolved_by": "operator@example.com",
            },
        )
        assert resp.status_code == 422

    def test_book_correction_mock_mode_honest_not_found(self, app_client: TestClient) -> None:
        resp = app_client.post(
            "/reporting/reconciliation/book-correction",
            json={"break_id": "BRK-001"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


class TestReconciliationBreaksRealModeProxy:
    def test_get_breaks_proxies_and_forwards_params(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.setenv(reporting._BLRS_SERVICE_URL_ENV, "http://blrs.test")
        monkeypatch.setattr(reporting.httpx, "AsyncClient", _FakeAsyncClient)
        _set_canned_response(httpx.Response(200, json=[{"break_id": "BRK-9", "venue": "OKX", "status": "pending"}]))

        resp = app_client.get("/reporting/reconciliation/breaks", params={"venue": "OKX", "status": "pending"})

        assert resp.status_code == 200, resp.text
        assert resp.json() == [{"break_id": "BRK-9", "venue": "OKX", "status": "pending"}]
        call = _FakeAsyncClient.last_call
        assert call is not None
        assert call["method"] == "GET"
        assert call["path"] == "/t1-recon/breaks"
        assert call["base_url"] == "http://blrs.test"
        assert call["params"] == {"venue": "OKX", "status": "pending"}

    def test_resolve_break_proxies_body_and_forwards_status(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.setenv(reporting._BLRS_SERVICE_URL_ENV, "http://blrs.test")
        monkeypatch.setattr(reporting.httpx, "AsyncClient", _FakeAsyncClient)
        _set_canned_response(
            httpx.Response(
                404,
                json={"detail": "Break BRK-404 not found"},
            )
        )

        resp = app_client.post(
            "/reporting/reconciliation/resolve",
            json={
                "break_id": "BRK-404",
                "action": "accept",
                "note": "expected timing divergence",
                "resolved_by": "operator@example.com",
            },
        )

        # BLRS's real 404 is forwarded verbatim, not masked as a mock-mode 200.
        assert resp.status_code == 404
        call = _FakeAsyncClient.last_call
        assert call is not None
        assert call["method"] == "POST"
        assert call["path"] == "/t1-recon/resolve"
        assert call["json"] == {
            "break_id": "BRK-404",
            "action": "accept",
            "note": "expected timing divergence",
            "resolved_by": "operator@example.com",
            "correcting_instruction_id": None,
        }

    def test_book_correction_proxies_and_forwards_success(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.setenv(reporting._BLRS_SERVICE_URL_ENV, "http://blrs.test")
        monkeypatch.setattr(reporting.httpx, "AsyncClient", _FakeAsyncClient)
        _set_canned_response(
            httpx.Response(
                200,
                json={
                    "venue": "Binance",
                    "instrument_id": "BTC-USDT",
                    "side": "BUY",
                    "quantity": 0.0045,
                    "execution_mode": "record_only",
                    "reason": "Correction for reconciliation break BRK-001",
                    "category": "",
                    "source_reference": "BRK-001",
                },
            )
        )

        resp = app_client.post(
            "/reporting/reconciliation/book-correction",
            json={"break_id": "BRK-001"},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["side"] == "BUY"
        call = _FakeAsyncClient.last_call
        assert call is not None
        assert call["path"] == "/t1-recon/book-correction"
        assert call["json"] == {"break_id": "BRK-001"}

    def test_no_blrs_url_configured_falls_back_to_mock(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app_client.app.state.mock_mode = False  # type: ignore[attr-defined]
        monkeypatch.delenv(reporting._BLRS_SERVICE_URL_ENV, raising=False)

        resp = app_client.post(
            "/reporting/reconciliation/book-correction",
            json={"break_id": "BRK-001"},
        )

        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


__all__: list[str] = []
