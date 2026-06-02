"""Plan C — HttpPbmPerformanceClient tests.

Validates the contract:
  * 200 with series → returns _PerViewSeries
  * 200 empty series → returns None (allows route fallback)
  * 404 → returns None
  * 5xx → returns None (no raise)
  * Network exception → returns None (no raise)
  * per_venue=True populates per_venue dict
  * make_pbm_performance_client factory → HttpPbmPerformanceClient for strategy-service URL
  * make_pbm_performance_client factory → SynthPbmPerformanceClient when base_url is None
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from unified_trading_api.routes.strategy_performance import (  # noqa: qg-deep-import — self-package
    SynthPbmPerformanceClient,
)
from unified_trading_api.services.pbm_performance import (
    HttpPbmPerformanceClient,
    make_pbm_performance_client,
)


def _client_with_handler(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://pbm.test")
    return HttpPbmPerformanceClient(base_url="http://pbm.test", http_client=http)


WINDOW_START = datetime(2026, 4, 1, tzinfo=UTC)
WINDOW_END = datetime(2026, 4, 25, tzinfo=UTC)


def test_get_series_returns_aggregate_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/accounts/odum-paper/pnl-series"
        assert request.url.params["instance_id"] == "inst_alpha"
        return httpx.Response(
            200,
            json={
                "account_id": "odum-paper",
                "instance_id": "inst_alpha",
                "series": [
                    {"timestamp": "2026-04-25T12:00:00+00:00", "pnl": 100.0, "venue": None},
                    {"timestamp": "2026-04-25T13:00:00+00:00", "pnl": 102.5, "venue": None},
                ],
            },
        )

    client = _client_with_handler(handler)
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_alpha",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is not None
    assert len(series.aggregate) == 2
    assert series.aggregate[0].pnl == 100.0
    assert series.per_venue is None


def test_get_series_per_venue_populated_when_requested() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["per_venue"] == "true"
        return httpx.Response(
            200,
            json={
                "series": [
                    {"timestamp": "2026-04-25T12:00:00+00:00", "pnl": 50.0, "venue": "BINANCE"},
                    {"timestamp": "2026-04-25T13:00:00+00:00", "pnl": 75.0, "venue": "OKX"},
                ],
            },
        )

    client = _client_with_handler(handler)
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_alpha",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=True,
    )
    assert series is not None
    assert series.per_venue is not None
    assert "BINANCE" in series.per_venue
    assert "OKX" in series.per_venue


def test_get_series_returns_none_on_empty_series() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"series": []})

    client = _client_with_handler(handler)
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_alpha",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is None


def test_get_series_returns_none_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "no data"})

    client = _client_with_handler(handler)
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_missing",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is None


def test_get_series_returns_none_on_5xx_does_not_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "store down"})

    client = _client_with_handler(handler)
    # Must NOT raise
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_alpha",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is None


def test_get_series_returns_none_on_network_error_does_not_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client_with_handler(handler)
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_alpha",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is None


def test_get_series_resolves_account_for_view_when_account_id_blank() -> None:
    captured_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "series": [{"timestamp": "2026-04-25T12:00:00+00:00", "pnl": 1.0, "venue": None}],
            },
        )

    client = _client_with_handler(handler)
    client.get_series(
        account_id="",
        instance_id="inst_alpha",
        view="live",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert captured_paths[0] == "/api/v1/accounts/odum-live/pnl-series"


def test_get_series_filters_invalid_entries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "series": [
                    {"timestamp": "2026-04-25T12:00:00+00:00", "pnl": 100.0, "venue": None},
                    {"timestamp": None, "pnl": 99.0, "venue": None},
                    {"timestamp": "2026-04-25T13:00:00+00:00", "pnl": "x", "venue": None},
                ],
            },
        )

    client = _client_with_handler(handler)
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_alpha",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is not None
    assert len(series.aggregate) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 422])
def test_get_series_returns_none_on_4xx_does_not_raise(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "fail"})

    client = _client_with_handler(handler)
    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_alpha",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is None


# ─── make_pbm_performance_client factory tests ────────────────────────────
# The factory wires to GET /api/v1/accounts/{account_id}/pnl-series on the
# strategy-service base URL (retired: http://position-balance-monitor:8080).


def test_factory_returns_http_client_when_base_url_provided() -> None:
    """Factory must produce HttpPbmPerformanceClient pointing at strategy-service."""
    client = make_pbm_performance_client(base_url="http://strategy-service:8080")
    assert isinstance(client, HttpPbmPerformanceClient)
    # The stored URL must be the strategy-service base (no trailing slash).
    assert client._base_url == "http://strategy-service:8080"  # pyright: ignore[reportPrivateUsage]


def test_factory_returns_synth_client_when_base_url_is_none() -> None:
    """Factory falls back to SynthPbmPerformanceClient when no URL is provided."""
    client = make_pbm_performance_client(base_url=None)
    assert isinstance(client, SynthPbmPerformanceClient)


def test_factory_http_client_calls_strategy_service_pnl_route() -> None:
    """End-to-end: factory-built client hits /api/v1/accounts/{id}/pnl-series."""
    captured_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "series": [
                    {"timestamp": "2026-04-25T12:00:00+00:00", "pnl": 42.0, "venue": None},
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    mock_http = httpx.Client(transport=transport, base_url="http://strategy-service:8080")
    client = make_pbm_performance_client(base_url="http://strategy-service:8080")
    # Inject the mock transport so the real HTTP call is intercepted.
    assert isinstance(client, HttpPbmPerformanceClient)
    client._client = mock_http  # pyright: ignore[reportPrivateUsage]

    series = client.get_series(
        account_id="odum-paper",
        instance_id="inst_beta",
        view="paper",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        per_venue=False,
    )
    assert series is not None
    assert len(series.aggregate) == 1
    assert series.aggregate[0].pnl == 42.0
    # Confirm the route path matches the strategy-service contract.
    assert captured_paths == ["/api/v1/accounts/odum-paper/pnl-series"]
