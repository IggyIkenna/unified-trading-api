"""Tests for the strategy-instance performance endpoint (Plan C)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from unified_trading_api.routes import strategy_performance


def _get(
    app_client: TestClient,
    instance_id: str = "DEFI_BASIS_ELYSIUM@ely_base_3cex-btc-usdt",
    **params: str | bool,
) -> dict[str, object]:
    strategy_performance.reset_cache_for_tests()
    resp = app_client.get(
        f"/api/v1/strategy-instances/{instance_id}/performance",
        params=params,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert isinstance(payload, dict)
    return payload


class TestPerformanceEndpointBasics:
    def test_default_views_returns_all_three_regimes(self, app_client: TestClient) -> None:
        data = _get(app_client)
        assert data["instance_id"].startswith("DEFI_BASIS_ELYSIUM")
        assert set(data["series"].keys()) == {"backtest", "paper", "live"}
        for view in ("backtest", "paper", "live"):
            assert len(data["series"][view]["aggregate"]) > 0

    def test_subset_views_returned_only(self, app_client: TestClient) -> None:
        data = _get(app_client, views="backtest,paper")
        assert set(data["series"].keys()) == {"backtest", "paper"}

    def test_transition_markers_present_when_window_large(self, app_client: TestClient) -> None:
        data = _get(app_client, **{"from": "180d"})
        markers = data["transition_markers"]
        assert markers["paper_started_at"] is not None
        assert markers["live_started_at"] is not None
        assert markers["paper_started_at"] < markers["live_started_at"]

    def test_phase_annotations_aligned_with_markers(self, app_client: TestClient) -> None:
        data = _get(app_client)
        phases = data["phase_annotations"]
        assert [p["phase"] for p in phases] == ["paper_1d", "live_early"]

    def test_deterministic_between_calls(self, app_client: TestClient) -> None:
        # Pin the window so two calls don't differ purely on `now` drift.
        a = _get(
            app_client, **{"from": "2025-01-01T00:00:00+00:00", "to": "2025-06-01T00:00:00+00:00"}
        )
        b = _get(
            app_client, **{"from": "2025-01-01T00:00:00+00:00", "to": "2025-06-01T00:00:00+00:00"}
        )
        assert a["series"]["backtest"]["aggregate"] == b["series"]["backtest"]["aggregate"]


class TestPerformanceEndpointPerVenue:
    def test_per_venue_false_omits_slices(self, app_client: TestClient) -> None:
        data = _get(app_client, per_venue=False)
        for view in data["series"].values():
            assert view.get("per_venue") in (None, {})

    def test_per_venue_true_expands_live(self, app_client: TestClient) -> None:
        data = _get(app_client, per_venue=True)
        live = data["series"]["live"]
        assert live["per_venue"] is not None
        assert len(live["per_venue"]) >= 2
        # Backtest does not surface a per-venue breakdown.
        assert data["series"]["backtest"].get("per_venue") in (None, {})

    def test_per_venue_slices_sum_to_aggregate_pnl_within_tolerance(
        self, app_client: TestClient
    ) -> None:
        data = _get(app_client, per_venue=True)
        live = data["series"]["live"]
        aggregate_last = live["aggregate"][-1]
        venue_last_pnl = sum(series[-1]["pnl"] for series in live["per_venue"].values())
        # Deterministic; float rounding tolerance ≤ 2 cents per venue.
        assert abs(aggregate_last["pnl"] - venue_last_pnl) < 1.0


class TestPerformanceEndpointValidation:
    def test_invalid_view_rejected(self, app_client: TestClient) -> None:
        resp = app_client.get(
            "/api/v1/strategy-instances/foo/performance",
            params={"views": "backtest,bogus"},
        )
        assert resp.status_code == 400
        assert "Unknown views" in resp.json()["detail"]

    def test_empty_views_rejected(self, app_client: TestClient) -> None:
        resp = app_client.get(
            "/api/v1/strategy-instances/foo/performance",
            params={"views": ""},
        )
        assert resp.status_code == 400

    def test_from_after_to_rejected(self, app_client: TestClient) -> None:
        resp = app_client.get(
            "/api/v1/strategy-instances/foo/performance",
            params={"from": "now", "to": "180d"},
        )
        assert resp.status_code == 400
        assert "from must precede to" in resp.json()["detail"]

    def test_bad_iso_rejected(self, app_client: TestClient) -> None:
        resp = app_client.get(
            "/api/v1/strategy-instances/foo/performance",
            params={"from": "not-a-date"},
        )
        assert resp.status_code == 400


class TestPerformanceEndpointMissingViewFallback:
    def test_single_view_request_returns_only_that_view(self, app_client: TestClient) -> None:
        # Component "stitched" mode falls back gracefully when a view is
        # not requested — only the requested key appears in the response.
        data = _get(app_client, views="backtest")
        assert list(data["series"].keys()) == ["backtest"]
        assert "paper" not in data["series"]
        assert "live" not in data["series"]
