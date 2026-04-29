"""Batch candle reader — reads pre-aggregated OHLCV bars from processed_candles/ in GCS.

Charts read processed candles only — never raw tick data, never request-time
aggregation. If a (date, timeframe, symbol) shard isn't backfilled, the reader
returns an empty list and the UI surfaces "no data" for that window. See
codex feedback: feedback_no_raw_data_for_charts.md.

Path layout (matches actual GCS reality, NOT the stale processing-service doc):
  bucket: market-data-tick-{cefi|tradfi|defi}-{project_id}
  prefix: processed_candles/by_date/day=YYYY-MM-DD/timeframe={tf}
                            /data_type={dtype}/venue={VENUE}/{symbol}.parquet

Schema (set by market-data-processing-service):
  timestamp (ts), open, high, low, close, volume, trade_count,
  buy_trade_count, sell_trade_count, buy_volume, sell_volume,
  delay_*_ms, instrument_id, symbol, venue

Manifest pruning: before issuing GCS reads, the reader consults
`_index/availability_index.parquet` (via UTL `read_availability_index`,
60s cached) to skip days that don't have a shard. Drops empty-day round
trips on weekends/holidays. Falls back gracefully if the manifest is
absent (returns the unfiltered candidate list).

Multi-day reads run in a small thread pool (GCS calls are I/O-bound, ~0.2 s
each). 30-day window cold-reads in well under a second.
"""

from __future__ import annotations

import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pyarrow.parquet as pq
from unified_trading_library import build_bucket, get_storage_client  # pyright: ignore[reportPrivateImportUsage]
from unified_trading_library.manifest_writer import read_availability_index

from unified_trading_api.config.curated_symbols import get_symbol_config  # noqa: qg-deep-import — self-package

# Bucket variant — `prod` (default) or `test`. Test variant appends "test-" to the
# bucket suffix per codex per-category-bucket-layouts.md. Same hive layout, different
# bucket name. Set MARKET_DATA_BUCKET_VARIANT=test to target test buckets.
_BUCKET_VARIANT = os.environ.get("MARKET_DATA_BUCKET_VARIANT", "prod")

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
    """Reads pre-aggregated OHLCV from GCS processed_candles/ shards.

    Single GCS read per (date, timeframe, symbol). No aggregation. Returns
    [] when a shard is missing — the UI's empty-state is the correct surface
    for that.
    """

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._storage = get_storage_client(project_id=project_id)
        self._tune_connection_pool()

    def _tune_connection_pool(self) -> None:
        """Bump the urllib3 connection pool size on the storage client.

        Default urllib3 pool size is 10. When ThreadPoolExecutor parallelises
        16 GCS reads, anything past 10 re-handshakes TLS — observed as
        ``Connection pool is full, discarding connection`` warnings and the
        10-day parallel scenario falling to ~4× single-day instead of 1×.
        Bumping to 32 covers the worker count + a small headroom.
        """
        from requests.adapters import HTTPAdapter

        # UTL wraps google-cloud-storage; the underlying client exposes
        # `_http` (an authorized requests Session). We mount a fresh adapter
        # with a wider pool so concurrent downloads share connections.
        try:
            inner = getattr(self._storage, "_client", None) or self._storage
            session = getattr(inner, "_http", None)
            if session is None:
                return
            adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32, max_retries=3)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        except Exception as exc:
            logger.debug("Could not tune connection pool: %s", exc)

    @staticmethod
    def _blob_path(
        venue: str,
        symbol: str,
        timeframe_partition: str,
        data_type: str,
        target_date: date,
    ) -> str:
        return (
            f"processed_candles/by_date/day={target_date.isoformat()}"
            f"/timeframe={timeframe_partition}/data_type={data_type}"
            f"/venue={venue}/{symbol}.parquet"
        )

    def _prune_dates_via_manifest(
        self,
        bucket: str,
        dates: list[date],
        data_type: str,
        timeframe_partition: str,
        venue: str,
        symbol: str,
    ) -> list[date]:
        """Filter `dates` to those with an MDPS manifest row for this shard.

        Manifest predicate matches the row that the rebuild script emits:
        service=MDPS, data_type, timeframe, venue, instrument_id (=symbol).

        If the manifest is empty (no rows at all) — bucket likely never
        had its index built — we don't prune. The downstream GCS read
        is the final source of truth and a missing shard returns [].
        """
        try:
            mdf = read_availability_index(bucket)
        except Exception as exc:
            logger.debug("Manifest read failed for %s; not pruning: %s", bucket, exc)
            return dates
        if mdf.empty:
            return dates

        mdps = mdf[mdf["service_name"] == "market-data-processing-service"]
        if mdps.empty:
            return dates

        # Match on the dimensions our rebuild script writes per file:
        #   data_type, timeframe, venue, instrument_id, available=True
        mdps = mdps[
            (mdps["data_type"] == data_type)
            & (mdps["timeframe"] == timeframe_partition)
            & (mdps["venue"] == venue)
            & (mdps["instrument_id"] == symbol)
            & (mdps["available"] == True)  # noqa: E712 — DataFrame mask
        ]
        if mdps.empty:
            # No rows for this exact shard — the manifest may simply not be
            # populated at this granularity yet (per-symbol underfill is
            # tracked as a follow-up). Fall back to no pruning.
            logger.debug(
                "Manifest has MDPS rows but none match (%s,%s,%s,%s); not pruning",
                data_type,
                timeframe_partition,
                venue,
                symbol,
            )
            return dates

        have = set(mdps["date"].astype(str).tolist())
        pruned = [d for d in dates if d.isoformat() in have]
        logger.debug("Manifest pruned %d → %d dates", len(dates), len(pruned))
        return pruned

    def _read_df(self, bucket: str, blob_path: str) -> pd.DataFrame | None:
        try:
            raw = self._storage.download_bytes(bucket=bucket, blob_path=blob_path)
            return pq.read_table(io.BytesIO(raw)).to_pandas()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        except Exception as exc:
            logger.debug("Blob read miss %s/%s: %s", bucket, blob_path, exc)
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
        """Return processed OHLCV candles for (venue, symbol, timeframe).

        Date precedence: as_of (single day) > from_date..to_date > yesterday.
        Reads one parquet per day. No raw aggregation. Empty result is a
        valid signal that the processing pipeline hasn't backfilled the
        requested window.
        """
        sym_config = get_symbol_config(venue, symbol)
        if sym_config is None:
            logger.warning("Symbol not in curated list: %s / %s", venue, symbol)
            return []

        timeframe_partition = _TIMEFRAME_MAP.get(timeframe)
        if timeframe_partition is None:
            logger.warning("Unsupported timeframe: %r", timeframe)
            return []

        category = _venue_to_category(venue)
        data_type = sym_config["data_type"]

        if as_of:
            dates: list[date] = [as_of]
        elif from_date and to_date:
            delta = (to_date - from_date).days
            dates = [from_date + timedelta(days=i) for i in range(delta + 1)]
        else:
            dates = [datetime.now(UTC).date() - timedelta(days=1)]

        try:
            bucket = build_bucket(
                "processed_candles", project_id=self._project_id, asset_group=category
            )
        except KeyError:
            logger.warning("Cannot build bucket for category '%s'", category)
            return []
        # Apply test-variant suffix when configured: market-data-tick-{cat}-{project}
        # → market-data-tick-{cat}-test-{project}. Hive layout identical.
        if _BUCKET_VARIANT == "test" and "-test-" not in bucket:
            bucket = bucket.replace(f"-{self._project_id}", f"-test-{self._project_id}")

        # Manifest-pruned date list: drop days that have no MDPS shard
        # registered. Falls back to the full candidate list if the manifest
        # is empty / unreadable so we never break a working request.
        dates = self._prune_dates_via_manifest(
            bucket=bucket,
            dates=dates,
            data_type=data_type,
            timeframe_partition=timeframe_partition,
            venue=venue,
            symbol=symbol,
        )
        if not dates:
            return []

        # Per-day GCS reads in parallel — they're independent and I/O-bound,
        # so a small thread pool turns N×0.2s into ~0.2s for the whole window.
        def _fetch(d: date) -> pd.DataFrame | None:
            blob = self._blob_path(venue, symbol, timeframe_partition, data_type, d)
            return self._read_df(bucket, blob)

        frames: list[pd.DataFrame] = []
        if len(dates) == 1:
            df = _fetch(dates[0])
            if df is not None and not df.empty:
                frames.append(df)
        else:
            workers = min(16, len(dates))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for df in ex.map(_fetch, dates):
                    if df is not None and not df.empty:
                        frames.append(df)

        if not frames:
            return []

        merged = pd.concat(frames, ignore_index=True)
        records = self._frame_to_records(merged)
        # Apply limit — keep the most recent `limit` bars
        if len(records) > limit:
            records = records[-limit:]
        return records
