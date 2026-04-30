"""Instruments-store reader — reads daily instrument-availability parquets from GCS.

In-memory 1h-TTL cache keyed by ``(asset_group, venue, as_of)``. Instruments
update at most once per day (instruments-service runs ``refresh-catalogue``
as a daily batch — see ``instruments-service/docs/instrument-catalogue.md``),
so a 1h TTL bounds GCS reads at ~15 per asset_group per hour.

Manifest pruning: when listing instruments across multiple venues for a
single date, the reader consults ``_index/availability_index.parquet`` (via
UTL ``read_availability_index``, 60s in-process cached) to learn which
``(date, venue)`` shards instruments-service actually published. Drops
empty-shard 404 round trips. Falls back to the unfiltered candidate list
when the manifest is empty (bucket never indexed) so a working request
never breaks.

Bucket variant: ``INSTRUMENTS_BUCKET_VARIANT`` env (``prod`` default,
``test`` opt-in). Test variant inserts ``-test-`` before project_id;
hive layout identical. Mirrors ``MARKET_DATA_BUCKET_VARIANT`` from
``batch_candles.py``.

Concurrency: when fanning out across venues for one date, reads run in a
small ``ThreadPoolExecutor`` (GCS calls are I/O-bound, ~50–200ms each).
Connection pool tuned at 32 to match ``BatchCandleReader``.
"""

from __future__ import annotations

import io
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pyarrow.parquet as pq
from unified_trading_library import build_bucket, get_storage_client  # pyright: ignore[reportPrivateImportUsage]
from unified_trading_library.manifest_writer import read_availability_index

logger = logging.getLogger(__name__)

_TTL_SECONDS = 3600.0

# Bucket variant — `prod` (default) or `test`. Test variant appends "test-"
# to the bucket suffix per codex per-category-bucket-layouts.md. Same hive
# layout, different bucket name. Set INSTRUMENTS_BUCKET_VARIANT=test to
# target test buckets.
_BUCKET_VARIANT = os.environ.get("INSTRUMENTS_BUCKET_VARIANT", "prod")


class InstrumentsReader:
    """Reads instrument availability from GCS with per-(group, venue, day) caching.

    Single-venue path: one GCS read per ``(asset_group, venue, as_of)``.
    Multi-venue path: ``list_venues_for_date`` + parallel fan-out via
    ``get_instruments_multi_venue``.
    Empty results pass through — the route returns ``[]`` and the UI shows
    its empty state.
    """

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._storage = get_storage_client(project_id=project_id)
        self._cache: dict[str, tuple[float, list[dict[str, object]]]] = {}
        self._tune_connection_pool()

    # ------------------------------------------------------------------
    # Connection-pool tune (mirrors BatchCandleReader)
    # ------------------------------------------------------------------

    def _tune_connection_pool(self) -> None:
        """Bump the urllib3 connection pool size on the storage client.

        Default urllib3 pool size is 10. When ``ThreadPoolExecutor``
        parallelises ~16 GCS reads, anything past 10 re-handshakes TLS —
        observed as ``Connection pool is full, discarding connection``
        warnings on the chart side. Bumping to 32 covers the worker count
        plus headroom.
        """
        from requests.adapters import HTTPAdapter

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

    # ------------------------------------------------------------------
    # Bucket resolution
    # ------------------------------------------------------------------

    def _resolve_bucket(self, category: str) -> str | None:
        """Build the bucket name for ``category``, applying variant suffix.

        ``prod`` → ``instruments-store-{cat}-{project_id}``
        ``test`` → ``instruments-store-{cat}-test-{project_id}``
        """
        try:
            bucket = build_bucket("instruments", project_id=self._project_id, asset_group=category)
        except KeyError:
            logger.warning("InstrumentsReader: unknown category '%s'", category)
            return None
        if _BUCKET_VARIANT == "test":
            # build_bucket produces "instruments-store-{cat}-{project_id}".
            # Insert "test-" before project_id to match codex test-mode pattern.
            bucket = bucket.replace(f"-{self._project_id}", f"-test-{self._project_id}")
        return bucket

    # ------------------------------------------------------------------
    # Public API — single venue
    # ------------------------------------------------------------------

    def get_instruments(
        self,
        asset_group: str,
        venue: str,
        as_of: date | None = None,
    ) -> list[dict[str, object]]:
        """Return instruments for (asset_group, venue, as_of). Defaults as_of to yesterday."""
        target_date = as_of or (datetime.now(UTC).date() - timedelta(days=1))
        cache_key = f"{asset_group.lower()}:{venue.upper()}:{target_date.isoformat()}"

        now = time.time()
        cached = self._cache.get(cache_key)
        if cached is not None and now - cached[0] < _TTL_SECONDS:
            return cached[1]

        records = self._fetch(asset_group.lower(), venue, target_date)
        self._cache[cache_key] = (now, records)
        return records

    # ------------------------------------------------------------------
    # Public API — multi-venue
    # ------------------------------------------------------------------

    def list_venues_for_date(
        self,
        asset_group: str,
        target_date: date,
    ) -> list[str]:
        """Return the venues that instruments-service published on ``target_date``.

        Reads the consolidated availability manifest for the bucket,
        filters to ``service_name == "instruments-service"`` and
        ``available == True`` rows for the requested date, returns the
        distinct venue list.

        Falls back to ``[]`` when the manifest is missing or empty — the
        caller can then decide to fan out across a hardcoded venue list
        or just return empty.
        """
        bucket = self._resolve_bucket(asset_group.lower())
        if bucket is None:
            return []
        try:
            mdf = read_availability_index(bucket)
        except Exception as exc:
            logger.debug("Manifest read failed for %s; cannot list venues: %s", bucket, exc)
            return []
        if mdf.empty:
            return []

        rows = mdf[
            (mdf["service_name"] == "instruments-service")
            & (mdf["date"].astype(str) == target_date.isoformat())
            & (mdf["available"] == True)  # noqa: E712 — DataFrame mask
        ]
        if rows.empty:
            return []
        venues = sorted(set(rows["venue"].astype(str).tolist()))
        # The manifest occasionally has empty-string venue rows (legacy
        # writers). Skip them — they're not useful here.
        return [v for v in venues if v]

    def latest_date_with_data(self, asset_group: str) -> date | None:
        """Return the most recent date that instruments-service has any shard for.

        Useful when the route's ``as_of`` is unset and we want the freshest
        available snapshot rather than guessing yesterday (which may be
        a weekend / holiday for TRADFI).
        """
        bucket = self._resolve_bucket(asset_group.lower())
        if bucket is None:
            return None
        try:
            mdf = read_availability_index(bucket)
        except Exception as exc:
            logger.debug("Manifest read failed for %s; cannot pick latest date: %s", bucket, exc)
            return None
        if mdf.empty:
            return None

        rows = mdf[
            (mdf["service_name"] == "instruments-service")
            & (mdf["available"] == True)  # noqa: E712 — DataFrame mask
        ]
        if rows.empty:
            return None
        # `date` column is YYYY-MM-DD string; lexical max == chronological max.
        latest_str = rows["date"].astype(str).max()
        try:
            return date.fromisoformat(str(latest_str))
        except ValueError:
            return None

    def get_instruments_multi_venue(
        self,
        asset_group: str,
        as_of: date | None = None,
        venues: list[str] | None = None,
    ) -> list[dict[str, object]]:
        """Fan out across venues for a single date, in parallel.

        - ``as_of`` defaults to ``latest_date_with_data(asset_group)``,
          falling back to yesterday if the manifest can't help.
        - ``venues`` defaults to ``list_venues_for_date(asset_group,
          target_date)`` — i.e. only venues with shards published.
        - Per-venue results merge into a single flat list. Each venue's
          fetch hits the same per-venue cache as the single-venue path.
        """
        if as_of is None:
            as_of = (
                self.latest_date_with_data(asset_group)
                or (datetime.now(UTC).date() - timedelta(days=1))
            )
        if venues is None:
            venues = self.list_venues_for_date(asset_group, as_of)
            if not venues:
                # Manifest empty — caller can still call get_instruments per
                # venue with a known list; here we return [] rather than
                # guess.
                logger.debug(
                    "Multi-venue: no venues in manifest for %s/%s; returning []",
                    asset_group,
                    as_of,
                )
                return []

        records: list[dict[str, object]] = []
        if len(venues) == 1:
            return self.get_instruments(asset_group, venues[0], as_of)

        workers = min(16, len(venues))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for venue_records in ex.map(
                lambda v: self.get_instruments(asset_group, v, as_of),
                venues,
            ):
                records.extend(venue_records)
        return records

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch(self, category: str, venue: str, target_date: date) -> list[dict[str, object]]:
        bucket = self._resolve_bucket(category)
        if bucket is None:
            return []
        blob = (
            f"instrument_availability/by_date/day={target_date.isoformat()}"
            f"/venue={venue}/instruments.parquet"
        )
        try:
            raw = self._storage.download_bytes(bucket=bucket, blob_path=blob)
        except Exception as exc:
            logger.debug(
                "InstrumentsReader: blob not found %s/%s: %s",
                bucket,
                blob,
                exc,
            )
            return []
        try:
            df = pq.read_table(io.BytesIO(raw)).to_pandas()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        except Exception as exc:
            logger.warning(
                "InstrumentsReader: parquet decode failed for %s/%s: %s",
                bucket,
                blob,
                exc,
            )
            return []
        return [self._normalise_row(row) for _, row in df.iterrows()]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType, reportUnknownMemberType]

    @staticmethod
    def _normalise_row(row: pd.Series) -> dict[str, object]:  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
        """Convert pandas Series → JSON-serialisable dict.

        Pandas-native types (Timestamp, Decimal, NaT, NaN, pd.NA, numpy scalars)
        are not directly JSON-encodable. Converts to ISO string / float / None.
        """
        result: dict[str, object] = {}
        for key, value in row.items():  # pyright: ignore[reportUnknownVariableType, reportAny]
            key_str = str(key)
            if value is None:
                result[key_str] = None
                continue
            # NaT / NaN / pd.NA — pd.isna only handles scalars, so guard against
            # collections that would yield an array of bools.
            if not isinstance(value, (list, dict, bytes, tuple)):
                try:
                    if pd.isna(value):  # pyright: ignore[reportAny]
                        result[key_str] = None
                        continue
                except (TypeError, ValueError):
                    pass
            if isinstance(value, pd.Timestamp):
                result[key_str] = value.isoformat()
            elif isinstance(value, Decimal):
                result[key_str] = float(value)
            else:
                # numpy scalar → python scalar via .item(). Skip for native Python types.
                item_attr = getattr(value, "item", None)  # pyright: ignore[reportUnknownArgumentType]
                if callable(item_attr) and not isinstance(value, (str, list, dict, bytes, tuple, bool, int, float)):
                    result[key_str] = item_attr()  # pyright: ignore[reportAny]
                else:
                    result[key_str] = value  # pyright: ignore[reportUnknownVariableType]
        return result
