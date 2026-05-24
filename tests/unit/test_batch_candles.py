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
    _TIMEFRAME_MAP,
    BatchCandleReader,
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
        assert _venue_to_category("UNISWAP_V3-ETHEREUM") == "defi"


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
            "processed_candles/by_date/day=2026-01-15/timeframe=5m/data_type=ohlcv_1m/venue=NASDAQ/AAPL.parquet"
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
            venue="NASDAQ",
            symbol="AAPL",
            timeframe="5m",
            limit=100,
            as_of=date(2026, 1, 15),
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
            venue="NASDAQ",
            symbol="AAPL",
            timeframe="5m",
            limit=100,
            as_of=date(2099, 1, 1),
        )
        assert bars == []
