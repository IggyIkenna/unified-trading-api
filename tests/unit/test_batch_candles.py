"""Tests for BatchCandleReader — processed-candles read path.

The reader points at processed_candles/ in GCS and returns whatever the
processing pipeline produced. No raw-trades aggregation, no client-side
resampling. Tests verify path construction, schema mapping, and the
"empty when missing" contract that drives the UI's no-data state.
"""

from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from unified_trading_api.services.batch_candles import (  # noqa: qg-deep-import — self-package
    BatchCandleReader,
    _TIMEFRAME_MAP,
    _venue_to_category,
)


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buf)
    return buf.getvalue()


class TestVenueToCategory:
    def test_cefi_venues(self) -> None:
        assert _venue_to_category("BINANCE-FUTURES") == "cefi"
        assert _venue_to_category("HYPERLIQUID") == "cefi"

    def test_tradfi_venues(self) -> None:
        assert _venue_to_category("NASDAQ") == "tradfi"
        assert _venue_to_category("NYSE") == "tradfi"

    def test_defi_venues(self) -> None:
        assert _venue_to_category("UNISWAPV3-ETHEREUM") == "defi"


class TestTimeframeMap:
    def test_ui_native_timeframes_map_to_partition_values(self) -> None:
        # The UI sends 1m/5m/15m/1H/4H/1D — pipeline writes 1m/5m/15m/1h/4h/24h
        assert _TIMEFRAME_MAP["1m"] == "1m"
        assert _TIMEFRAME_MAP["5m"] == "5m"
        assert _TIMEFRAME_MAP["15m"] == "15m"
        assert _TIMEFRAME_MAP["1H"] == "1h"
        assert _TIMEFRAME_MAP["4H"] == "4h"
        assert _TIMEFRAME_MAP["1D"] == "24h"


class TestBlobPath:
    def test_path_layout_matches_processing_service_doc(self) -> None:
        path = BatchCandleReader._blob_path(
            venue="NASDAQ",
            symbol="AAPL",
            timeframe_partition="5m",
            data_type="ohlcv_1m",
            target_date=date(2026, 1, 15),
        )
        assert path == (
            "processed_candles/by_date/day=2026-01-15"
            "/timeframe=5m/data_type=ohlcv_1m"
            "/venue=NASDAQ/AAPL.parquet"
        )


class TestGetCandles:
    def test_unknown_symbol_returns_empty(self) -> None:
        with patch("unified_trading_api.services.batch_candles.get_storage_client"):
            reader = BatchCandleReader(project_id="p")
        result = reader.get_candles(venue="MADE-UP-VENUE", symbol="FOOBAR", timeframe="1H")
        assert result == []

    def test_unsupported_timeframe_returns_empty(self) -> None:
        with patch("unified_trading_api.services.batch_candles.get_storage_client"):
            reader = BatchCandleReader(project_id="p")
        # Use a curated symbol so the symbol check passes; fail on timeframe
        result = reader.get_candles(venue="NASDAQ", symbol="AAPL", timeframe="3w")
        assert result == []

    def test_processed_shard_is_returned_verbatim_no_resample(self) -> None:
        # Simulate a processed_candles parquet — already aggregated 5m bars.
        ts0 = pd.Timestamp("2026-01-15T13:30:00Z")
        df = pd.DataFrame(
            {
                "timestamp": [ts0, ts0 + pd.Timedelta(minutes=5)],
                "open": [180.00, 180.50],
                "high": [180.80, 180.90],
                "low": [179.80, 180.30],
                "close": [180.50, 180.70],
                "volume": [10000.0, 12500.0],
                "instrument_id": ["NASDAQ:EQUITY:AAPL-USD", "NASDAQ:EQUITY:AAPL-USD"],
                "symbol": ["AAPL", "AAPL"],
                "venue": ["NASDAQ", "NASDAQ"],
            }
        )
        parquet_bytes = _make_parquet_bytes(df)
        mock_storage = MagicMock()
        mock_storage.download_bytes.return_value = parquet_bytes
        with patch(
            "unified_trading_api.services.batch_candles.get_storage_client",
            return_value=mock_storage,
        ):
            reader = BatchCandleReader(project_id="p")
        bars = reader.get_candles(
            venue="NASDAQ", symbol="AAPL", timeframe="5m",
            limit=100, as_of=date(2026, 1, 15),
        )
        # Bars come back unchanged — no resampling, no aggregation
        assert len(bars) == 2
        assert bars[0]["open"] == 180.00
        assert bars[0]["close"] == 180.50
        assert bars[0]["volume"] == 10000.0
        assert bars[1]["high"] == 180.90
        # Returns Unix-second timestamps for chart consumption
        assert bars[1]["time"] == int(ts0.timestamp()) + 300

    def test_missing_shard_returns_empty(self) -> None:
        # The user-facing contract: no shard → empty list, NOT a 500 or fallback.
        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = FileNotFoundError("404 No such object")
        with patch(
            "unified_trading_api.services.batch_candles.get_storage_client",
            return_value=mock_storage,
        ):
            reader = BatchCandleReader(project_id="p")
        bars = reader.get_candles(
            venue="NASDAQ", symbol="AAPL", timeframe="5m",
            limit=100, as_of=date(2099, 1, 1),
        )
        assert bars == []


class TestManifestPruning:
    """Manifest-driven pruning skips empty days before issuing GCS reads."""

    def test_empty_manifest_does_not_prune(self) -> None:
        """If the manifest is empty (bucket never indexed), don't prune. GCS
        is the final source of truth and missing shards return []."""
        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = FileNotFoundError("404")
        with patch(
            "unified_trading_api.services.batch_candles.get_storage_client",
            return_value=mock_storage,
        ), patch(
            "unified_trading_api.services.batch_candles.read_availability_index",
            return_value=pd.DataFrame(),
        ):
            reader = BatchCandleReader(project_id="p")
            bars = reader.get_candles(
                venue="NASDAQ", symbol="AAPL", timeframe="5m",
                limit=100,
                from_date=date(2026, 1, 13), to_date=date(2026, 1, 15),
            )
        # No shards exist (mock 404s every read) → empty result, but GCS reads
        # were still attempted (3 downloads — one per day in the unfiltered
        # window).
        assert bars == []
        assert mock_storage.download_bytes.call_count == 3

    def test_manifest_filters_to_present_days(self) -> None:
        """Days not in the manifest are skipped — no GCS read attempted."""
        manifest = pd.DataFrame(
            [
                {
                    "service_name": "market-data-processing-service",
                    "data_type": "ohlcv_1m",
                    "timeframe": "5m",
                    "venue": "NASDAQ",
                    "instrument_id": "AAPL",
                    "available": True,
                    "date": "2026-01-13",
                },
                # 2026-01-14 deliberately missing
                {
                    "service_name": "market-data-processing-service",
                    "data_type": "ohlcv_1m",
                    "timeframe": "5m",
                    "venue": "NASDAQ",
                    "instrument_id": "AAPL",
                    "available": True,
                    "date": "2026-01-15",
                },
                # Also a row for a different symbol — must NOT match
                {
                    "service_name": "market-data-processing-service",
                    "data_type": "ohlcv_1m",
                    "timeframe": "5m",
                    "venue": "NASDAQ",
                    "instrument_id": "MSFT",
                    "available": True,
                    "date": "2026-01-14",
                },
            ]
        )
        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = FileNotFoundError("404")
        with patch(
            "unified_trading_api.services.batch_candles.get_storage_client",
            return_value=mock_storage,
        ), patch(
            "unified_trading_api.services.batch_candles.read_availability_index",
            return_value=manifest,
        ):
            reader = BatchCandleReader(project_id="p")
            _ = reader.get_candles(
                venue="NASDAQ", symbol="AAPL", timeframe="5m",
                limit=100,
                from_date=date(2026, 1, 13), to_date=date(2026, 1, 15),
            )
        # 3-day window pruned to 2 (13th + 15th present, 14th + MSFT match
        # filtered out).
        assert mock_storage.download_bytes.call_count == 2

    def test_no_matching_rows_falls_back_to_unfiltered(self) -> None:
        """Manifest exists but has nothing for our exact (data_type, tf, venue,
        symbol) tuple — don't prune; fall back to GCS attempts."""
        manifest = pd.DataFrame(
            [
                {
                    "service_name": "market-data-processing-service",
                    "data_type": "trades",  # different
                    "timeframe": "5m",
                    "venue": "NASDAQ",
                    "instrument_id": "AAPL",
                    "available": True,
                    "date": "2026-01-13",
                },
            ]
        )
        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = FileNotFoundError("404")
        with patch(
            "unified_trading_api.services.batch_candles.get_storage_client",
            return_value=mock_storage,
        ), patch(
            "unified_trading_api.services.batch_candles.read_availability_index",
            return_value=manifest,
        ):
            reader = BatchCandleReader(project_id="p")
            _ = reader.get_candles(
                venue="NASDAQ", symbol="AAPL", timeframe="5m",
                limit=100,
                from_date=date(2026, 1, 13), to_date=date(2026, 1, 14),
            )
        # No matching MDPS rows for (ohlcv_1m, 5m, NASDAQ, AAPL) — no pruning.
        # Both days attempted.
        assert mock_storage.download_bytes.call_count == 2


class TestBucketVariant:
    """MARKET_DATA_BUCKET_VARIANT switches between prod and test buckets."""

    def test_test_variant_appends_test_to_bucket_name(self) -> None:
        from unified_trading_api.services import batch_candles as bc

        captured: dict[str, str] = {}

        def _capture_download(*, bucket: str, blob_path: str) -> bytes:
            captured["bucket"] = bucket
            raise FileNotFoundError("404 — capturing the bucket name")

        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = _capture_download
        with patch.object(bc, "_BUCKET_VARIANT", "test"), patch.object(
            bc, "get_storage_client", return_value=mock_storage
        ), patch.object(bc, "read_availability_index", return_value=pd.DataFrame()):
            reader = bc.BatchCandleReader(project_id="proj")
            _ = reader.get_candles(
                venue="NASDAQ", symbol="AAPL", timeframe="5m",
                limit=100, as_of=date(2026, 1, 15),
            )
        # Test variant inserts -test- before the project id
        assert "-test-proj" in captured["bucket"]
        assert "tradfi" in captured["bucket"]

    def test_prod_variant_default_no_suffix(self) -> None:
        from unified_trading_api.services import batch_candles as bc

        captured: dict[str, str] = {}

        def _capture_download(*, bucket: str, blob_path: str) -> bytes:
            captured["bucket"] = bucket
            raise FileNotFoundError("404")

        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = _capture_download
        with patch.object(bc, "_BUCKET_VARIANT", "prod"), patch.object(
            bc, "get_storage_client", return_value=mock_storage
        ), patch.object(bc, "read_availability_index", return_value=pd.DataFrame()):
            reader = bc.BatchCandleReader(project_id="proj")
            _ = reader.get_candles(
                venue="NASDAQ", symbol="AAPL", timeframe="5m",
                limit=100, as_of=date(2026, 1, 15),
            )
        assert "-test-" not in captured["bucket"]
        assert captured["bucket"].endswith("-proj")
