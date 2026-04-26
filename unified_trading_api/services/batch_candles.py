"""Batch candle reader — reads raw tick data from GCS and aggregates to OHLCV bars."""

from __future__ import annotations

import io
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Literal

import pandas as pd
import pyarrow.parquet as pq
from unified_trading_library import build_bucket, get_storage_client  # pyright: ignore[reportPrivateImportUsage]

from unified_trading_api.config.curated_symbols import get_symbol_config  # noqa: qg-deep-import — self-package

logger = logging.getLogger(__name__)

# Map API/frontend timeframe string → pandas resample rule
_RESAMPLE_RULES: dict[str, str] = {
    "1m": "1min",
    "1M": "1min",
    "5m": "5min",
    "5M": "5min",
    "15m": "15min",
    "15M": "15min",
    "30m": "30min",
    "30M": "30min",
    "1H": "1h",
    "1h": "1h",
    "4H": "4h",
    "4h": "4h",
    "1D": "1D",
    "1d": "1D",
}

_CEFI_VENUE_PREFIXES: tuple[str, ...] = (
    "BINANCE", "BYBIT", "DERIBIT", "OKX", "HYPERLIQUID", "COINBASE", "KRAKEN", "BITMEX",
)
_TRADFI_VENUE_PREFIXES: tuple[str, ...] = ("CME", "NYSE", "NASDAQ", "ICE", "CBOE", "FX")
_DEFI_VENUE_PREFIXES: tuple[str, ...] = (
    "UNISWAP", "AAVE", "CURVE", "LIDO", "MORPHO", "COMPOUND", "BALANCER", "SUSHI",
)


def _venue_to_category(venue: str) -> str:
    vu = venue.upper()
    if any(vu.startswith(p) for p in _CEFI_VENUE_PREFIXES):
        return "cefi"
    if any(vu.startswith(p) for p in _TRADFI_VENUE_PREFIXES):
        return "tradfi"
    if any(vu.startswith(p) for p in _DEFI_VENUE_PREFIXES):
        return "defi"
    return "cefi"


class BatchCandleReader:
    """Reads OHLCV candles from GCS raw tick data, aggregating trades/prices to bars."""

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._storage = get_storage_client(project_id=project_id)

    def _blob_path(
        self,
        category: str,
        venue: str,
        instrument_type: str,
        data_type: str,
        symbol: str,
        target_date: date,
        chain: str = "",
    ) -> str:
        date_str = target_date.isoformat()
        if category == "defi" and chain:
            return (
                f"raw_tick_data/by_date/day={date_str}/category={category}"
                f"/chain={chain}/venue={venue}/instrument_type={instrument_type}"
                f"/data_type={data_type}/{symbol}.parquet"
            )
        return (
            f"raw_tick_data/by_date/day={date_str}/category={category}"
            f"/venue={venue}/instrument_type={instrument_type}"
            f"/data_type={data_type}/{symbol}.parquet"
        )

    def _read_df(
        self,
        bucket: str,
        blob_path: str,
        columns: list[str] | None = None,
    ) -> pd.DataFrame | None:
        try:
            raw = self._storage.download_bytes(bucket=bucket, blob_path=blob_path)
            return pq.read_table(io.BytesIO(raw), columns=columns).to_pandas()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        except Exception as exc:
            logger.debug("Blob read failed %s/%s: %s", bucket, blob_path, exc)
            return None

    @staticmethod
    def _detect_trade_schema(
        df: pd.DataFrame,
    ) -> tuple[str, Literal["us", "ns"], str, str]:
        """Detect (time_col, time_unit, price_col, size_col) from a trades DataFrame.

        Tardis CEFI archive: ``timestamp`` (us), ``price``, ``amount``.
        Databento / canonical pipeline: ``ts_event`` (ns), ``price``, ``size``.
        Oracle prices: ``timestamp`` (us) + ``price``, no size column.
        """
        cols = set(df.columns)
        if "timestamp" in cols:
            time_col: str = "timestamp"
            time_unit: Literal["us", "ns"] = "us"
        else:
            time_col = "ts_event"
            time_unit = "ns"
        if "amount" in cols:
            size_col = "amount"
        elif "size" in cols:
            size_col = "size"
        elif "volume" in cols:
            size_col = "volume"
        else:
            size_col = ""
        return time_col, time_unit, "price", size_col

    def _aggregate_trades(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """Convert raw trades (price + size + timestamp) to OHLCV bars."""
        time_col, time_unit, price_col, size_col = self._detect_trade_schema(df)
        df = df.copy()
        df["__ts"] = pd.to_datetime(df[time_col], unit=time_unit, utc=True)
        df = df.set_index("__ts").sort_index()
        ohlcv = df[price_col].resample(rule).agg(open="first", high="max", low="min", close="last")
        if size_col:
            ohlcv["volume"] = df[size_col].resample(rule).sum()
        else:
            ohlcv["volume"] = 0.0
        return ohlcv.dropna(subset=["open"])  # pyright: ignore[reportCallIssue, reportUnknownVariableType]

    def _aggregate_ohlcv(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """Resample native OHLCV to a larger timeframe."""
        cols = set(df.columns)
        if "ts_event" in cols:
            time_col: str = "ts_event"
            time_unit: Literal["us", "ns"] = "ns"
        else:
            time_col = "timestamp"
            time_unit = "us"
        df = df.copy()
        df["__ts"] = pd.to_datetime(df[time_col], unit=time_unit, utc=True)
        df = df.set_index("__ts").sort_index()
        result = pd.DataFrame(
            {
                "open": df["open"].resample(rule).first(),
                "high": df["high"].resample(rule).max(),
                "low": df["low"].resample(rule).min(),
                "close": df["close"].resample(rule).last(),
                "volume": df["volume"].resample(rule).sum(),
            }
        )
        return result.dropna(subset=["open"])  # pyright: ignore[reportCallIssue, reportUnknownVariableType]

    def _to_records(self, df: pd.DataFrame, limit: int) -> list[dict[str, object]]:
        df = df.tail(limit)
        records: list[dict[str, object]] = []
        for ts, row in df.iterrows():
            records.append(
                {
                    "time": int(pd.Timestamp(ts).timestamp()),  # type: ignore[arg-type]
                    "open": float(row["open"]),  # pyright: ignore[reportAny]
                    "high": float(row["high"]),  # pyright: ignore[reportAny]
                    "low": float(row["low"]),  # pyright: ignore[reportAny]
                    "close": float(row["close"]),  # pyright: ignore[reportAny]
                    "volume": float(row.get("volume", 0.0)),  # type: ignore[call-overload]
                }
            )
        return records

    def get_candles(
        self,
        venue: str,
        symbol: str,
        timeframe: str = "1H",
        limit: int = 200,
        as_of: date | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, object]]:
        """Return OHLCV candles for (venue, symbol) aggregated to timeframe.

        Date precedence: as_of (single day) > from_date..to_date > yesterday.
        """
        sym_config = get_symbol_config(venue, symbol)
        if sym_config is None:
            logger.warning("Symbol not in curated list: %s / %s", venue, symbol)
            return []

        rule = _RESAMPLE_RULES.get(timeframe, "1h")
        category = _venue_to_category(venue)
        instrument_type = sym_config["instrument_type"]
        data_type = sym_config["data_type"]
        chain = sym_config.get("chain", "")

        if as_of:
            dates: list[date] = [as_of]
        elif from_date and to_date:
            delta = (to_date - from_date).days
            dates = [from_date + timedelta(days=i) for i in range(delta + 1)]
        else:
            dates = [datetime.now(UTC).date() - timedelta(days=1)]

        try:
            bucket = build_bucket("raw_tick_data", project_id=self._project_id, category=category)
        except KeyError:
            logger.warning("Cannot build bucket for category '%s'", category)
            return []

        frames: list[pd.DataFrame] = []
        for target_date in dates:
            blob = self._blob_path(category, venue, instrument_type, data_type, symbol, target_date, chain)
            # No column projection: source schemas vary (Tardis vs Databento) and
            # mismatched names error in pyarrow. _aggregate_* sniffs columns from the frame.
            df = self._read_df(bucket, blob)
            if df is None or df.empty:
                continue
            if data_type == "ohlcv_1m":
                frames.append(self._aggregate_ohlcv(df, rule))
            else:
                frames.append(self._aggregate_trades(df, rule))

        if not frames:
            return []

        merged = pd.concat(frames).sort_index()
        return self._to_records(merged, limit)
