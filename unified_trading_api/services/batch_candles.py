"""Batch candle reader — reads pre-aggregated OHLCV bars from processed_candles/ in GCS.

Charts read processed candles only — never raw tick data, never request-time
aggregation. If a (date, timeframe, symbol) shard isn't backfilled, the reader
returns an empty list and the UI surfaces "no data" for that window. See
codex feedback: feedback_no_raw_data_for_charts.md.

Path layout (matches market-data-processing-service docs/GCS_PATHS.md):
  bucket: market-data-tick-{cefi|tradfi|defi}-{project_id}
  prefix: processed_candles/by_date/day=YYYY-MM-DD/timeframe={tf}
                            /data_type={dtype}/venue={VENUE}/{symbol}.parquet

MDPS candle canonical migration (2026-07-20+, operator-ruled OPTION A): the LOCKED shape adds an
`instrument_type={it}/` segment (after data_type=, before venue=). Both shapes coexist during the
migration window, so reads DUAL-READ via `unified_trading_library.candle_read_prefixes()` — the
canonical (with instrument_type=) prefix is probed first, falling back to the legacy (without)
prefix. `data_type` stays the SOURCE type in both variants (no aggregated-key mapping here).

Schema (set by market-data-processing-service):
  timestamp (ts), open, high, low, close, volume, trade_count,
  buy_trade_count, sell_trade_count, buy_volume, sell_volume,
  delay_*_ms, instrument_id, symbol, venue

Multi-day reads run in a small thread pool (GCS calls are I/O-bound, ~0.2 s
each). 30-day window cold-reads in well under a second.
"""

from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pyarrow.parquet as pq
from unified_api_contracts import GRAIN_BUNDLE_BY_UNDERLYING, grain_for_instrument_type
from unified_trading_library import (  # pyright: ignore[reportPrivateImportUsage]
    build_bucket,
    candle_read_prefixes,
    get_storage_client,
)

from unified_trading_api.config.curated_symbols import (  # noqa: qg-deep-import — self-package
    get_symbol_config,
)

logger = logging.getLogger(__name__)

# Map UI/frontend timeframe string → processed_candles partition value.
# The processing pipeline writes 15s/1m/5m/15m/1h/4h/24h. The UI sends
# 1m/5m/15m/1H/4H/1D etc., so we normalise here.
_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "1M": "1m",
    "5m": "5m",
    "5M": "5m",
    "15m": "15m",
    "15M": "15m",
    "1H": "1h",
    "1h": "1h",
    "4H": "4h",
    "4h": "4h",
    "1D": "24h",
    "1d": "24h",
    "24h": "24h",
}

_CEFI_VENUE_PREFIXES: tuple[str, ...] = (
    "BINANCE",
    "BYBIT",
    "DERIBIT",
    "OKX",
    "HYPERLIQUID",
    "COINBASE",
    "KRAKEN",
    "BITMEX",
)
_TRADFI_VENUE_PREFIXES: tuple[str, ...] = ("CME", "NYSE", "NASDAQ", "ICE", "CBOE", "FX")
_DEFI_VENUE_PREFIXES: tuple[str, ...] = (
    "UNISWAP",
    "AAVE",
    "CURVE",
    "LIDO",
    "MORPHO",
    "COMPOUND",
    "BALANCER",
    "SUSHI",
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
    """Reads pre-aggregated OHLCV from GCS processed_candles/ shards.

    Single GCS read per (date, timeframe, symbol). No aggregation. Returns
    [] when a shard is missing — the UI's empty-state is the correct surface
    for that.
    """

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._storage = get_storage_client(project_id=project_id)

    @staticmethod
    def _blob_path_candidates(
        venue: str,
        symbol: str,
        timeframe_partition: str,
        data_type: str,
        target_date: date,
        instrument_type: str | None,
    ) -> list[str]:
        """Return candle object paths to probe, canonical (instrument_type=) first.

        Delegates prefix construction to ``candle_read_prefixes()`` so the migration's
        with/without-``instrument_type=`` shapes are never hand-duplicated here. ``data_type``
        is passed as both the aggregated and source key (kept as the SOURCE type — this call
        site has no aggregated-key mapping); ``pipeline_mode`` is omitted (not tracked at this
        call site, matching the pre-migration flat path).

        Tail: a chain-bundle instrument (per UAC's ``grain_for_instrument_type`` capture-grain
        SSOT — e.g. TradFi FUTURE at CME/ICE) is captured MDPS-side as a per-underlying bundle,
        never a flat per-symbol parquet, so its tail is ``underlying={symbol}/ticks.parquet``
        (the curated symbol IS already the underlying root, e.g. CME "ES") instead of
        ``{symbol}.parquet``. Was previously always-flat regardless of instrument_type — the
        same silent-miss bug class as
        candle_delta_one_chain_bundle_data_type_detection_silent_miss_2026_07_27.md's
        delta_one ``DataLoader`` finding, applied here to this dual-reader.
        """
        prefixes = candle_read_prefixes(
            date=target_date.isoformat(),
            timeframe=timeframe_partition,
            data_type_aggregated=data_type,
            data_type_source=data_type,
            instrument_type=instrument_type,
            venue=venue,
            pipeline_mode=None,
        )
        is_chain_bundle = (
            instrument_type is not None
            and grain_for_instrument_type(_venue_to_category(venue), instrument_type, venue=venue)
            == GRAIN_BUNDLE_BY_UNDERLYING
        )
        tail = f"underlying={symbol}/ticks.parquet" if is_chain_bundle else f"{symbol}.parquet"
        return [f"{prefix}{tail}" for prefix in prefixes]

    def _read_df(self, bucket: str, blob_path: str) -> pd.DataFrame | None:
        try:
            raw = self._storage.download_bytes(bucket=bucket, blob_path=blob_path)
            return pq.read_table(io.BytesIO(raw)).to_pandas()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        except Exception as exc:
            logger.debug("Blob read miss %s/%s: %s", bucket, blob_path, exc)
            return None

    def _read_first_available(self, bucket: str, blob_paths: list[str]) -> pd.DataFrame | None:
        """Try each candidate path in order (canonical first); return the first hit."""
        for blob_path in blob_paths:
            df = self._read_df(bucket, blob_path)
            if df is not None:
                return df
        return None

    @staticmethod
    def _frame_to_records(df: pd.DataFrame) -> list[dict[str, object]]:
        """Convert a processed-candles DataFrame to chart-friendly OHLCV dicts.

        The processed schema has `timestamp` (datetime), `open/high/low/close/volume`.
        TRADFI shards include rows for outside-RTH minutes with NaN OHLC; those
        get dropped here so the chart never receives null bars.
        """
        if df.empty:
            return []
        # Normalise column names: some shards may have `ts` or `timestamp`
        ts_col = "timestamp" if "timestamp" in df.columns else "ts"
        # Drop rows where the bar didn't actually trade (NaN OHLC).
        df = df.dropna(subset=["open", "high", "low", "close"])  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
        if df.empty:
            return []
        df = df.sort_values(by=ts_col)
        records: list[dict[str, object]] = []
        for _, row in df.iterrows():
            ts_val = row[ts_col]  # pyright: ignore[reportUnknownVariableType, reportAny]
            unix_sec = int(pd.Timestamp(ts_val).timestamp())  # pyright: ignore[reportUnknownArgumentType, reportAny]
            records.append(
                {
                    "time": unix_sec,
                    "open": float(row["open"]),  # pyright: ignore[reportAny]
                    "high": float(row["high"]),  # pyright: ignore[reportAny]
                    "low": float(row["low"]),  # pyright: ignore[reportAny]
                    "close": float(row["close"]),  # pyright: ignore[reportAny]
                    "volume": float(row.get("volume", 0.0)),  # pyright: ignore[reportAny]
                }
            )
        return records

    @staticmethod
    def _resolve_dates(as_of: date | None, from_date: date | None, to_date: date | None) -> list[date]:
        """Pick the date window per the precedence: as_of > from_date..to_date > yesterday."""
        if as_of:
            return [as_of]
        if from_date and to_date:
            delta = (to_date - from_date).days
            return [from_date + timedelta(days=i) for i in range(delta + 1)]
        return [datetime.now(UTC).date() - timedelta(days=1)]

    def _fetch_frames(
        self,
        dates: list[date],
        *,
        bucket: str,
        venue: str,
        symbol: str,
        timeframe_partition: str,
        data_type: str,
        instrument_type: str | None,
    ) -> list[pd.DataFrame]:
        """Read one parquet per day, in parallel for multi-day windows. Drops empty/missing days.

        Each day dual-reads: canonical (instrument_type=) candidate first, legacy fallback second.
        """

        def _fetch(d: date) -> pd.DataFrame | None:
            candidates = self._blob_path_candidates(venue, symbol, timeframe_partition, data_type, d, instrument_type)
            return self._read_first_available(bucket, candidates)

        frames: list[pd.DataFrame] = []
        if len(dates) == 1:
            df = _fetch(dates[0])
            if df is not None and not df.empty:
                frames.append(df)
            return frames
        workers = min(16, len(dates))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for df in ex.map(_fetch, dates):
                if df is not None and not df.empty:
                    frames.append(df)
        return frames

    def _resolve_bucket(self, asset_group: str) -> str | None:
        """Build the raw-tick-data bucket name for ``asset_group``; log + return
        ``None`` when no mapping exists so the caller treats the read as empty."""
        try:
            return build_bucket("raw_tick_data", project_id=self._project_id, asset_group=asset_group)
        except KeyError:
            logger.warning("Cannot build bucket for asset_group '%s'", asset_group)
            return None

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
        """Return processed OHLCV candles for (venue, symbol, timeframe).

        Date precedence: as_of (single day) > from_date..to_date > yesterday.
        Reads one parquet per day. No raw aggregation. Empty result signals the
        processing pipeline hasn't backfilled the requested window.
        """
        sym_config = get_symbol_config(venue, symbol)
        if sym_config is None:
            logger.warning("Symbol not in curated list: %s / %s", venue, symbol)
            return []
        timeframe_partition = _TIMEFRAME_MAP.get(timeframe)
        if timeframe_partition is None:
            logger.warning("Unsupported timeframe: %r", timeframe)
            return []
        asset_group = _venue_to_category(venue)
        bucket = self._resolve_bucket(asset_group)
        if bucket is None:
            return []

        frames = self._fetch_frames(
            self._resolve_dates(as_of, from_date, to_date),
            bucket=bucket,
            venue=venue,
            symbol=symbol,
            timeframe_partition=timeframe_partition,
            data_type=sym_config["data_type"],
            instrument_type=sym_config.get("instrument_type"),
        )
        if not frames:
            return []
        records = self._frame_to_records(pd.concat(frames, ignore_index=True))
        return records[-limit:] if len(records) > limit else records
