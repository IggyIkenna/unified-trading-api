"""Tests for InstrumentsReader — GCS path, type normalisation, caching."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from unified_trading_api.services.instruments_reader import (  # noqa: qg-deep-import — self-package
    InstrumentsReader,
)


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buf)
    return buf.getvalue()


def _build_reader_with_parquet(parquet_bytes: bytes | Exception) -> tuple[InstrumentsReader, MagicMock]:
    mock_storage = MagicMock()
    if isinstance(parquet_bytes, Exception):
        mock_storage.download_bytes.side_effect = parquet_bytes
    else:
        mock_storage.download_bytes.return_value = parquet_bytes
    with patch(
        "unified_trading_api.services.instruments_reader.get_storage_client",
        return_value=mock_storage,
    ):
        reader = InstrumentsReader(project_id="proj-x")
    return reader, mock_storage


class TestNormalisation:
    def test_timestamps_become_iso_strings(self) -> None:
        df = pd.DataFrame({
            "instrument_key": ["A:B:C"],
            "available_from_datetime": [pd.Timestamp("2026-04-14T00:00:00", tz="UTC")],
            "available_to_datetime": [pd.NaT],
        })
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        records = reader.get_instruments(asset_group="cefi", venue="X", as_of=date(2026, 4, 14))
        assert len(records) == 1
        row = records[0]
        assert row["instrument_key"] == "A:B:C"
        assert isinstance(row["available_from_datetime"], str)
        assert "2026-04-14" in str(row["available_from_datetime"])
        assert row["available_to_datetime"] is None

    def test_decimals_become_floats(self) -> None:
        df = pd.DataFrame({
            "instrument_key": ["A:B:C"],
            "tick_size": [Decimal("0.01")],
            "min_size": [Decimal("0.001")],
        })
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        records = reader.get_instruments(asset_group="cefi", venue="X", as_of=date(2026, 4, 14))
        assert records[0]["tick_size"] == 0.01
        assert records[0]["min_size"] == 0.001
        assert isinstance(records[0]["tick_size"], float)


class TestCache:
    def test_second_call_hits_cache(self) -> None:
        df = pd.DataFrame({"instrument_key": ["A:B:C"], "venue": ["X"]})
        reader, mock_storage = _build_reader_with_parquet(_make_parquet_bytes(df))
        _ = reader.get_instruments(asset_group="cefi", venue="X", as_of=date(2026, 4, 14))
        _ = reader.get_instruments(asset_group="cefi", venue="X", as_of=date(2026, 4, 14))
        # Storage should only be hit once
        assert mock_storage.download_bytes.call_count == 1

    def test_different_keys_miss_cache(self) -> None:
        df = pd.DataFrame({"instrument_key": ["A:B:C"], "venue": ["X"]})
        reader, mock_storage = _build_reader_with_parquet(_make_parquet_bytes(df))
        _ = reader.get_instruments(asset_group="cefi", venue="X", as_of=date(2026, 4, 14))
        _ = reader.get_instruments(asset_group="cefi", venue="Y", as_of=date(2026, 4, 14))
        assert mock_storage.download_bytes.call_count == 2


class TestEmpty:
    def test_blob_not_found_returns_empty(self) -> None:
        reader, _ = _build_reader_with_parquet(FileNotFoundError("404"))
        records = reader.get_instruments(asset_group="cefi", venue="X", as_of=date(2099, 1, 1))
        assert records == []


# ---------------------------------------------------------------------------
# New methods added 2026-04-30 for the watchlist plan (Unit A) — manifest
# pruning + parallel multi-venue fan-out.
# ---------------------------------------------------------------------------


def _manifest_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build a manifest DataFrame matching read_availability_index's shape."""
    cols = ["service_name", "date", "venue", "available"]
    return pd.DataFrame([{c: r.get(c, "") for c in cols} for r in rows])


class TestListVenuesForDate:
    """list_venues_for_date should return venues from the manifest filtered
    to instruments-service rows on the requested date with available=True."""

    def test_returns_distinct_venues_for_target_date(self) -> None:
        df = pd.DataFrame({"instrument_key": ["A:B:C"]})
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        manifest = _manifest_df([
            {"service_name": "instruments-service", "date": "2026-04-14", "venue": "BINANCE-FUTURES", "available": True},
            {"service_name": "instruments-service", "date": "2026-04-14", "venue": "BYBIT", "available": True},
            {"service_name": "instruments-service", "date": "2026-04-13", "venue": "OKX-SPOT", "available": True},  # wrong date
            {"service_name": "instruments-service", "date": "2026-04-14", "venue": "DERIBIT", "available": False},  # not available
            {"service_name": "market-tick-data-service", "date": "2026-04-14", "venue": "BINANCE-SPOT", "available": True},  # wrong service
        ])
        with patch(
            "unified_trading_api.services.instruments_reader.read_availability_index",
            return_value=manifest,
        ):
            venues = reader.list_venues_for_date("cefi", date(2026, 4, 14))
        assert venues == ["BINANCE-FUTURES", "BYBIT"]

    def test_empty_manifest_returns_empty_list(self) -> None:
        df = pd.DataFrame({"instrument_key": ["A:B:C"]})
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        with patch(
            "unified_trading_api.services.instruments_reader.read_availability_index",
            return_value=pd.DataFrame(),
        ):
            venues = reader.list_venues_for_date("cefi", date(2026, 4, 14))
        assert venues == []

    def test_manifest_read_failure_returns_empty(self) -> None:
        """If read_availability_index throws (e.g. no bucket access), we
        return [] rather than crashing the caller."""
        df = pd.DataFrame({"instrument_key": ["A:B:C"]})
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        with patch(
            "unified_trading_api.services.instruments_reader.read_availability_index",
            side_effect=PermissionError("nope"),
        ):
            venues = reader.list_venues_for_date("cefi", date(2026, 4, 14))
        assert venues == []


class TestLatestDateWithData:
    """latest_date_with_data picks the max date string in the manifest
    (filtered to instruments-service + available=True). Lexical max ==
    chronological max for YYYY-MM-DD strings."""

    def test_picks_max_date(self) -> None:
        df = pd.DataFrame({"instrument_key": ["A:B:C"]})
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        manifest = _manifest_df([
            {"service_name": "instruments-service", "date": "2026-04-10", "venue": "BINANCE-FUTURES", "available": True},
            {"service_name": "instruments-service", "date": "2026-04-14", "venue": "BYBIT", "available": True},
            {"service_name": "instruments-service", "date": "2026-04-12", "venue": "OKX-SPOT", "available": True},
        ])
        with patch(
            "unified_trading_api.services.instruments_reader.read_availability_index",
            return_value=manifest,
        ):
            assert reader.latest_date_with_data("cefi") == date(2026, 4, 14)

    def test_empty_manifest_returns_none(self) -> None:
        df = pd.DataFrame({"instrument_key": ["A:B:C"]})
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        with patch(
            "unified_trading_api.services.instruments_reader.read_availability_index",
            return_value=pd.DataFrame(),
        ):
            assert reader.latest_date_with_data("cefi") is None


class TestGetInstrumentsMultiVenue:
    """Parallel fan-out across venues. Each venue resolves its own per-(group,
    venue, day) cache so per-venue results merge correctly."""

    def test_fans_out_across_manifest_venues(self) -> None:
        # Each venue gets its own parquet bytes — return based on the blob path.
        venue_btc = pd.DataFrame({"instrument_key": ["BINANCE-FUTURES:PERPETUAL:BTC-USDT"], "venue": ["BINANCE-FUTURES"]})
        venue_eth = pd.DataFrame({"instrument_key": ["BYBIT:PERPETUAL:ETH-USDT"], "venue": ["BYBIT"]})

        def fake_download(*, bucket: str, blob_path: str) -> bytes:
            del bucket  # unused
            if "venue=BINANCE-FUTURES" in blob_path:
                return _make_parquet_bytes(venue_btc)
            if "venue=BYBIT" in blob_path:
                return _make_parquet_bytes(venue_eth)
            raise FileNotFoundError(f"no fixture for {blob_path}")

        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = fake_download
        with patch(
            "unified_trading_api.services.instruments_reader.get_storage_client",
            return_value=mock_storage,
        ):
            reader = InstrumentsReader(project_id="proj-x")

        manifest = _manifest_df([
            {"service_name": "instruments-service", "date": "2026-04-14", "venue": "BINANCE-FUTURES", "available": True},
            {"service_name": "instruments-service", "date": "2026-04-14", "venue": "BYBIT", "available": True},
        ])
        with patch(
            "unified_trading_api.services.instruments_reader.read_availability_index",
            return_value=manifest,
        ):
            records = reader.get_instruments_multi_venue("cefi", as_of=date(2026, 4, 14))

        keys = sorted(str(r["instrument_key"]) for r in records)
        assert keys == ["BINANCE-FUTURES:PERPETUAL:BTC-USDT", "BYBIT:PERPETUAL:ETH-USDT"]

    def test_empty_manifest_returns_empty(self) -> None:
        df = pd.DataFrame({"instrument_key": ["A:B:C"]})
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        with patch(
            "unified_trading_api.services.instruments_reader.read_availability_index",
            return_value=pd.DataFrame(),
        ):
            records = reader.get_instruments_multi_venue("cefi", as_of=date(2026, 4, 14))
        assert records == []

    def test_explicit_venues_override_manifest(self) -> None:
        """Caller can pass venues= explicitly to skip the manifest lookup."""
        df = pd.DataFrame({"instrument_key": ["BINANCE-FUTURES:PERPETUAL:BTC-USDT"]})
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        # No manifest patch — the test would fail on read_availability_index
        # if the code path consulted it. Explicit venues= must short-circuit.
        records = reader.get_instruments_multi_venue(
            "cefi",
            as_of=date(2026, 4, 14),
            venues=["BINANCE-FUTURES"],
        )
        assert len(records) == 1
