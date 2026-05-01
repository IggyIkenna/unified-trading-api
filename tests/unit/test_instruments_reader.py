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


def _build_reader_with_parquet(
    parquet_bytes: bytes | Exception,
) -> tuple[InstrumentsReader, MagicMock]:
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
        df = pd.DataFrame(
            {
                "instrument_key": ["A:B:C"],
                "available_from_datetime": [pd.Timestamp("2026-04-14T00:00:00", tz="UTC")],
                "available_to_datetime": [pd.NaT],
            }
        )
        reader, _ = _build_reader_with_parquet(_make_parquet_bytes(df))
        records = reader.get_instruments(asset_group="cefi", venue="X", as_of=date(2026, 4, 14))
        assert len(records) == 1
        row = records[0]
        assert row["instrument_key"] == "A:B:C"
        assert isinstance(row["available_from_datetime"], str)
        assert "2026-04-14" in str(row["available_from_datetime"])
        assert row["available_to_datetime"] is None

    def test_decimals_become_floats(self) -> None:
        df = pd.DataFrame(
            {
                "instrument_key": ["A:B:C"],
                "tick_size": [Decimal("0.01")],
                "min_size": [Decimal("0.001")],
            }
        )
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
