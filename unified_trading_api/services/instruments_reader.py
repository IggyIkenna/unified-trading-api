"""Instruments-store reader — reads daily instrument-availability parquets from GCS.

In-memory 1h-TTL cache keyed by ``(asset_group, venue, as_of)``. Instruments
update at most a few times per day, so a 1h TTL bounds GCS reads at
~15 per asset_group per hour.
"""

from __future__ import annotations

import io
import logging
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pyarrow.parquet as pq
from unified_trading_library import (  # pyright: ignore[reportPrivateImportUsage]
    build_bucket,
    get_storage_client,
)

logger = logging.getLogger(__name__)

_TTL_SECONDS = 3600.0


class InstrumentsReader:
    """Reads instrument availability from GCS with per-(group, venue, day) caching."""

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._storage = get_storage_client(project_id=project_id)
        self._cache: dict[str, tuple[float, list[dict[str, object]]]] = {}

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

    def _fetch(self, asset_group: str, venue: str, target_date: date) -> list[dict[str, object]]:
        try:
            bucket = build_bucket("instruments", project_id=self._project_id, asset_group=asset_group)
        except KeyError:
            logger.warning("InstrumentsReader: unknown asset_group '%s'", asset_group)
            return []
        blob = f"instrument_availability/by_date/day={target_date.isoformat()}/venue={venue}/instruments.parquet"
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
