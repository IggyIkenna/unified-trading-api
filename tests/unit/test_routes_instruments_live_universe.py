"""Tests for GET /instruments/live-universe route.

Covers:
- 200 in mock mode for each asset_group (returns mock seed envelope).
- 422 when asset_group is missing.
- Real mode: dedupe by instrument_key (Tardis multi-fiat-rail collapse guard).
- Real mode: live filter drops instruments with available_to_datetime in the past.
- Real mode: returns [] cleanly when no reader / no project_id.
- INSTRUMENTS_BUCKET_VARIANT env routes to *-test-* bucket.

Storage is fully mocked. No GCS calls.

Plan: unified-trading-pm/plans/ai/watchlist_from_instruments_2026_04_29.plan.md Unit C
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Mock-mode behaviour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("asset_group", ["cefi", "tradfi", "defi"])
def test_mock_mode_returns_200_per_asset_group(app_client: TestClient, asset_group: str) -> None:
    resp = app_client.get(f"/instruments/live-universe?asset_group={asset_group}")
    assert resp.status_code == 200
    body = resp.json()
    # Envelope contract — see test_live_universe_schema for full assertions.
    assert "data" in body and isinstance(body["data"], list)
    assert body["asset_group"] == asset_group
    assert "total" in body


def test_missing_asset_group_returns_422(app_client: TestClient) -> None:
    """asset_group is a required query param."""
    resp = app_client.get("/instruments/live-universe")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Real-mode dedupe — guards against URDI Tardis multi-fiat-rail collapse
# (see findings/instruments_tardis_duplicate_keys_2026_04_30.md)
# ---------------------------------------------------------------------------


def _row(key: str, available_to: str | None = None) -> dict[str, object]:
    """Minimal live-universe row for tests."""
    return {
        "instrument_key": key,
        "venue": "BINANCE-FUTURES",
        "raw_symbol": key.split(":")[-1],
        "instrument_type": "PERPETUAL",
        "available_to_datetime": available_to,
    }


def test_real_mode_dedupes_duplicate_instrument_keys(app_client: TestClient) -> None:
    """Reader returns 3 rows with the same instrument_key (the Tardis bug).
    Route should emit exactly 1 row.
    """
    duplicated_records = [
        _row("OKX-SPOT:SPOT_PAIR:BTC-USD"),
        _row("OKX-SPOT:SPOT_PAIR:BTC-USD"),
        _row("OKX-SPOT:SPOT_PAIR:BTC-USD"),
    ]
    mock_reader = MagicMock()
    mock_reader.latest_date_with_data.return_value = datetime.now(UTC).date()
    mock_reader.get_instruments_multi_venue.return_value = duplicated_records

    with patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False), patch(
        "unified_trading_api.routes.instruments.get_mock_mode", return_value=False
    ), patch(
        "unified_trading_api.routes.instruments._get_instruments_reader", return_value=mock_reader
    ):
        resp = app_client.get("/instruments/live-universe?asset_group=cefi")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1, f"expected 1 row after dedupe, got {len(body['data'])}"
    assert body["total"] == 1


# ---------------------------------------------------------------------------
# Real-mode live filter — drops expired instruments
# ---------------------------------------------------------------------------


def test_real_mode_drops_expired_instruments(app_client: TestClient) -> None:
    """available_to_datetime in the past → not in response."""
    past_iso = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    future_iso = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    records = [
        _row("DERIBIT:OPTION:BTC-EXPIRED-1", available_to=past_iso),
        _row("DERIBIT:OPTION:BTC-EXPIRED-2", available_to=past_iso),
        _row("DERIBIT:PERPETUAL:BTC", available_to=None),  # active
        _row("DERIBIT:OPTION:BTC-FUTURE", available_to=future_iso),  # future expiry
    ]
    mock_reader = MagicMock()
    mock_reader.latest_date_with_data.return_value = datetime.now(UTC).date()
    mock_reader.get_instruments_multi_venue.return_value = records

    with patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False), patch(
        "unified_trading_api.routes.instruments.get_mock_mode", return_value=False
    ), patch(
        "unified_trading_api.routes.instruments._get_instruments_reader", return_value=mock_reader
    ):
        resp = app_client.get("/instruments/live-universe?asset_group=cefi")

    assert resp.status_code == 200
    body = resp.json()
    keys = [r["instrument_key"] for r in body["data"]]
    assert "DERIBIT:PERPETUAL:BTC" in keys, "active perpetual must remain"
    assert "DERIBIT:OPTION:BTC-FUTURE" in keys, "future expiry must remain"
    assert "DERIBIT:OPTION:BTC-EXPIRED-1" not in keys, "past expiry must be filtered"
    assert "DERIBIT:OPTION:BTC-EXPIRED-2" not in keys, "past expiry must be filtered"


# ---------------------------------------------------------------------------
# Real-mode graceful degradation
# ---------------------------------------------------------------------------


def test_real_mode_no_reader_returns_empty_envelope(app_client: TestClient) -> None:
    """When InstrumentsReader can't be constructed (no project_id), the
    route returns an empty data payload rather than 500. UI sees the
    "no instruments available" empty state.
    """
    with patch(
        "unified_trading_api.routes.instruments.get_mock_mode", return_value=False
    ), patch(
        "unified_trading_api.routes.instruments._get_instruments_reader", return_value=None
    ):
        resp = app_client.get("/instruments/live-universe?asset_group=cefi")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []


# ---------------------------------------------------------------------------
# Bucket variant routing
# ---------------------------------------------------------------------------


def test_bucket_variant_test_routes_to_test_bucket() -> None:
    """INSTRUMENTS_BUCKET_VARIANT=test inserts -test- before project_id.

    Asserted at the reader level — easier than threading through the
    route. The route just instantiates the reader; the reader resolves
    the bucket name.
    """
    with patch.dict(os.environ, {"INSTRUMENTS_BUCKET_VARIANT": "test"}, clear=False):
        # Re-import to pick up the env at module load.
        import importlib

        from unified_trading_api.services import instruments_reader as ir_module
        importlib.reload(ir_module)
        from unified_trading_api.services.instruments_reader import InstrumentsReader

        with patch("unified_trading_api.services.instruments_reader.get_storage_client"):
            reader = InstrumentsReader(project_id="my-proj")
        bucket = reader._resolve_bucket("cefi")
        assert bucket is not None
        assert "-test-" in bucket, f"expected -test- in bucket, got {bucket!r}"
        assert "my-proj" in bucket

    # Restore default (prod) so other tests aren't affected.
    with patch.dict(os.environ, {"INSTRUMENTS_BUCKET_VARIANT": "prod"}, clear=False):
        import importlib

        from unified_trading_api.services import instruments_reader as ir_module
        importlib.reload(ir_module)


def test_bucket_variant_prod_default() -> None:
    """Default (no env) is prod — no -test- suffix."""
    # Ensure clean env
    env_no_variant = {k: v for k, v in os.environ.items() if k != "INSTRUMENTS_BUCKET_VARIANT"}
    with patch.dict(os.environ, env_no_variant, clear=True):
        import importlib

        from unified_trading_api.services import instruments_reader as ir_module
        importlib.reload(ir_module)
        from unified_trading_api.services.instruments_reader import InstrumentsReader

        with patch("unified_trading_api.services.instruments_reader.get_storage_client"):
            reader = InstrumentsReader(project_id="my-proj")
        bucket = reader._resolve_bucket("cefi")
        assert bucket is not None
        assert "-test-" not in bucket, f"prod bucket must not contain -test-, got {bucket!r}"
