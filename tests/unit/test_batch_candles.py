"""Tests for BatchCandleReader — GCS path construction, schema detection, OHLCV aggregation."""

from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from unified_trading_api.services.batch_candles import (  # noqa: qg-deep-import — self-package
    BatchCandleReader,
    _RESAMPLE_RULES,
    _venue_to_category,
)


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Round-trip a DataFrame to parquet bytes for use in mocks."""
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buf)
    return buf.getvalue()


class TestVenueToCategory:
    def test_cefi_venues(self) -> None:
        assert _venue_to_category("BINANCE-FUTURES") == "cefi"
        assert _venue_to_category("HYPERLIQUID") == "cefi"
        assert _venue_to_category("DERIBIT") == "cefi"

    def test_tradfi_venues(self) -> None:
        assert _venue_to_category("CME") == "tradfi"
        assert _venue_to_category("NASDAQ") == "tradfi"

    def test_defi_venues(self) -> None:
        assert _venue_to_category("UNISWAPV3-ETHEREUM") == "defi"
        assert _venue_to_category("AAVEV3-ETHEREUM") == "defi"

    def test_unknown_falls_back_to_cefi(self) -> None:
        assert _venue_to_category("UNKNOWN-VENUE") == "cefi"


class TestResampleRules:
    def test_covers_ui_native_strings(self) -> None:
        # The UI sends 1m/5m/15m/1H/4H/1D — the API must accept all.
        for tf in ("1m", "5m", "15m", "1H", "4H", "1D"):
            assert tf in _RESAMPLE_RULES, f"Missing resample rule for {tf}"


class TestBlobPath:
    def test_cefi_path(self) -> None:
        with patch("unified_trading_api.services.batch_candles.get_storage_client"):
            reader = BatchCandleReader(project_id="proj-x")
        blob = reader._blob_path("cefi", "BINANCE-FUTURES", "perpetual", "trades", "BTCUSDT", date(2026, 4, 14))
        assert blob == (
            "raw_tick_data/by_date/day=2026-04-14/category=cefi"
            "/venue=BINANCE-FUTURES/instrument_type=perpetual"
            "/data_type=trades/BTCUSDT.parquet"
        )

    def test_defi_path_with_chain(self) -> None:
        with patch("unified_trading_api.services.batch_candles.get_storage_client"):
            reader = BatchCandleReader(project_id="proj-x")
        blob = reader._blob_path(
            "defi", "UNISWAPV3-ETHEREUM", "lp_pool", "oracle_prices",
            "WETH-USDC-500", date(2026, 4, 14), chain="ethereum",
        )
        assert "/chain=ethereum/" in blob
        assert blob.endswith("WETH-USDC-500.parquet")


class TestTradeSchemaDetection:
    def test_tardis_format_detected(self) -> None:
        df = pd.DataFrame({"timestamp": [1, 2, 3], "price": [1.0, 2.0, 3.0], "amount": [0.1, 0.2, 0.3]})
        time_col, time_unit, price_col, size_col = BatchCandleReader._detect_trade_schema(df)
        assert time_col == "timestamp"
        assert time_unit == "us"
        assert price_col == "price"
        assert size_col == "amount"

    def test_databento_format_detected(self) -> None:
        df = pd.DataFrame({"ts_event": [1, 2, 3], "price": [1.0, 2.0, 3.0], "size": [0.1, 0.2, 0.3]})
        time_col, time_unit, _, size_col = BatchCandleReader._detect_trade_schema(df)
        assert time_col == "ts_event"
        assert time_unit == "ns"
        assert size_col == "size"

    def test_oracle_prices_no_size_column(self) -> None:
        df = pd.DataFrame({"timestamp": [1, 2, 3], "price": [1.0, 2.0, 3.0]})
        _, _, _, size_col = BatchCandleReader._detect_trade_schema(df)
        assert size_col == ""


class TestTradeAggregation:
    def test_resample_to_ohlcv(self) -> None:
        # 4 trades all within the same 1-minute bucket (use a known-aligned epoch).
        # base = 1700000000_000_000 us → 2023-11-14 22:13:20 UTC
        base = 1_700_000_000_000_000
        ts_us = [base + 0, base + 5_000_000, base + 10_000_000, base + 15_000_000]
        df = pd.DataFrame({
            "timestamp": ts_us,
            "price": [100.0, 105.0, 95.0, 102.0],
            "amount": [1.0, 2.0, 3.0, 1.5],
        })
        with patch("unified_trading_api.services.batch_candles.get_storage_client"):
            reader = BatchCandleReader(project_id="p")
        out = reader._aggregate_trades(df, "5min")
        # All 4 trades fall in the same 5-minute bar, so OHLCV should be one row.
        assert len(out) == 1
        row = out.iloc[0]
        assert row["open"] == 100.0
        assert row["high"] == 105.0
        assert row["low"] == 95.0
        assert row["close"] == 102.0
        assert row["volume"] == 7.5


class TestGetCandles:
    def test_unknown_symbol_returns_empty(self) -> None:
        with patch("unified_trading_api.services.batch_candles.get_storage_client"):
            reader = BatchCandleReader(project_id="p")
        result = reader.get_candles(venue="MADE-UP-VENUE", symbol="FOOBAR", timeframe="1H")
        assert result == []

    def test_curated_symbol_aggregates_to_ohlcv(self) -> None:
        # Build a synthetic Tardis-format trades parquet
        ts_us = [1_776_124_800_000_000 + i * 1_000_000_000 for i in range(60)]
        df = pd.DataFrame({
            "timestamp": ts_us,
            "price": [70_000.0 + i * 10 for i in range(60)],
            "amount": [1.0] * 60,
            "exchange": ["binance-futures"] * 60,
            "symbol": ["btcusdt"] * 60,
        })
        parquet_bytes = _make_parquet_bytes(df)

        mock_storage = MagicMock()
        mock_storage.download_bytes.return_value = parquet_bytes
        with patch(
            "unified_trading_api.services.batch_candles.get_storage_client",
            return_value=mock_storage,
        ):
            reader = BatchCandleReader(project_id="proj-x")
        candles = reader.get_candles(
            venue="BINANCE-FUTURES",
            symbol="BTCUSDT",
            timeframe="1m",
            limit=100,
            as_of=date(2026, 4, 14),
        )
        assert len(candles) >= 1
        first = candles[0]
        # OHLCV shape
        assert {"time", "open", "high", "low", "close", "volume"} <= set(first.keys())
        assert isinstance(first["time"], int)
        # Open should equal first trade price (within the bar)
        assert first["open"] == 70_000.0


class TestEmptyResult:
    def test_blob_not_found_returns_empty(self) -> None:
        mock_storage = MagicMock()
        mock_storage.download_bytes.side_effect = FileNotFoundError("404")
        with patch(
            "unified_trading_api.services.batch_candles.get_storage_client",
            return_value=mock_storage,
        ):
            reader = BatchCandleReader(project_id="proj-x")
        candles = reader.get_candles(
            venue="BINANCE-FUTURES",
            symbol="BTCUSDT",
            timeframe="1H",
            as_of=date(2099, 1, 1),
        )
        assert candles == []
