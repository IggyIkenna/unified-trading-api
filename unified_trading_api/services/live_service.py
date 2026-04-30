"""GCS-backed DomainService for live/batch mode.

Replaces the LiveDomainService stub with a real implementation that reads
from GCS via UTL's cloud_interface. Collection names with mode suffix
(e.g., "positions_live", "fills_batch") are resolved to GCS paths via
the PATH_REGISTRY.

Read-only for GCS-backed collections. Write operations (create/update/delete)
are no-ops that log warnings — mutations go through individual services, not
the API gateway.
"""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime

import pandas as pd
from unified_trading_library import build_bucket, get_storage_client

logger = logging.getLogger(__name__)


# Map collection base names → PATH_REGISTRY dataset names
_COLLECTION_TO_DATASET: dict[str, str] = {
    "positions": "positions",
    "orders": "strategy_orders",
    "fills": "execution_fills",
    "risk": "risk_metrics",
    "pnl": "pnl_attribution",
}

# Map dataset → GCS prefix template (date + mode level only, for scanning)
_DATASET_PREFIX: dict[str, str] = {
    "positions": "by_date/day={date}/mode={mode}/",
    "strategy_orders": "strategy_orders/by_date/day={date}/mode={mode}/",
    "execution_fills": "execution/by_date/day={date}/mode={mode}/",
    "risk_metrics": "by_date/day={date}/mode={mode}/",
    "pnl_attribution": "by_date/day={date}/mode={mode}/",
}

# Collections not backed by mode-partitioned GCS (return empty in live mode)
_STATIC_COLLECTIONS: frozenset[str] = frozenset(
    {
        "position_summary",
        "balances",
        "risk_limits",
        "var",
        "greeks",
        "stress_tests",
        "exposure_types",
        "defi_health",
        "correlation_matrix",
        "regime",
        "execution_venues",
        "algos",
        "grid_configs",
        "backtests",
        "strategies",
        "performance",
        "analytics_organizations",
        "settlements",
        "analytics_instruments",
        "sports_bets",
        "defi_operations",
        "alerts",
        "pnl_timeseries",
    }
)


class GcsDomainService:
    """Domain service reading from GCS with mode-aware path resolution.

    Collection names follow the pattern ``{domain}_{mode}`` (e.g.,
    ``positions_live``, ``fills_batch``). The service:

    1. Parses the collection name to extract domain + mode
    2. Resolves to a GCS bucket + prefix via the PATH_REGISTRY
    3. Lists and reads all parquet files under that prefix
    4. Applies client-side filters (venue, strategy_id, etc.)
    5. Returns records as ``list[dict]``
    """

    def __init__(self, project_id: str, category: str = "cefi") -> None:
        self._project_id = project_id
        self._category = category
        self._storage = get_storage_client(project_id=project_id)

    @staticmethod
    def _parse_collection(collection: str) -> tuple[str, str]:
        """Parse ``positions_live`` → ``("positions", "live")``.

        Collections without a mode suffix default to ``"live"``.
        """
        for suffix in ("_live", "_batch"):
            if collection.endswith(suffix):
                return collection[: -len(suffix)], suffix[1:]
        return collection, "live"

    def _read_parquet_prefix(
        self,
        bucket: str,
        prefix: str,
    ) -> list[dict[str, object]]:
        """List all ``.parquet`` files under *prefix*, read and merge them."""
        try:
            blobs = self._storage.list_blobs(bucket, prefix=prefix)
            parquet_blobs = [b for b in blobs if b.name.endswith(".parquet")]
        except (ConnectionError, TimeoutError, OSError, ValueError) as exc:
            logger.warning("GCS list failed for %s/%s: %s", bucket, prefix, exc)
            return []

        if not parquet_blobs:
            return []

        frames: list[pd.DataFrame] = []
        for blob in parquet_blobs:
            try:
                raw = self._storage.download_bytes(bucket, blob.name)
                df = pd.read_parquet(io.BytesIO(raw))
                frames.append(df)
            except (ConnectionError, TimeoutError, OSError, ValueError) as exc:
                logger.warning("Failed to read %s/%s: %s", bucket, blob.name, exc)
                continue

        if not frames:
            return []

        merged = pd.concat(frames, ignore_index=True)
        records: list[dict[str, object]] = merged.to_dict(orient="records")  # pyright: ignore[reportAssignmentType]
        return records

    @staticmethod
    def _apply_filters(
        records: list[dict[str, object]],
        filters: dict[str, str | int | float | bool | None] | None,
    ) -> list[dict[str, object]]:
        """Apply key-value filters, skipping None values and control keys."""
        if not filters:
            return records
        result: list[dict[str, object]] = []
        for record in records:
            match = True
            for key, value in filters.items():
                # Skip None values and the as_of control key
                if value is None or key == "as_of":
                    continue
                if record.get(key) != value:
                    match = False
                    break
            if match:
                result.append(record)
        return result

    # ---------------------------------------------------------------------- #
    # DomainService protocol
    # ---------------------------------------------------------------------- #

    def list(
        self,
        collection: str,
        filters: dict[str, str | int | float | bool | None] | None = None,
    ) -> list[dict[str, object]]:
        """List records from GCS for the given collection.

        For mode-partitioned collections (positions, orders, fills, risk, pnl),
        reads all parquet files under ``gs://{bucket}/{prefix}/day={date}/mode={mode}/``
        and applies client-side filters.

        Pass ``as_of`` in *filters* to override the date (defaults to today).
        """
        base_name, mode = self._parse_collection(collection)

        # Static collections without GCS backing
        if base_name in _STATIC_COLLECTIONS or collection in _STATIC_COLLECTIONS:
            return []

        dataset = _COLLECTION_TO_DATASET.get(base_name)
        if not dataset:
            logger.debug("No dataset mapping for collection '%s'", collection)
            return []

        # Determine date: as_of filter (batch) or today (live).
        # Guard against None — str(None) is "None" (truthy) and would inject
        # the literal string into the GCS path.
        raw_as_of = filters.get("as_of") if filters else None
        as_of = str(raw_as_of) if raw_as_of else ""
        date_str = as_of[:10] if as_of else datetime.now(UTC).strftime("%Y-%m-%d")

        # Resolve bucket
        try:
            bucket = build_bucket(dataset, project_id=self._project_id, asset_group=self._category)
        except KeyError:
            logger.warning("Cannot build bucket for dataset '%s'", dataset)
            return []

        # Build prefix for scanning
        prefix_template = _DATASET_PREFIX.get(dataset, "by_date/day={date}/mode={mode}/")
        prefix = prefix_template.format(date=date_str, mode=mode)

        records = self._read_parquet_prefix(bucket, prefix)
        return self._apply_filters(records, filters)

    def get(self, collection: str, record_id: str) -> dict[str, object] | None:
        """Get a single record by ID (scans via list)."""
        records = self.list(collection)
        for record in records:
            if record.get("id") == record_id:
                return record
        return None

    def create(self, collection: str, data: dict[str, object]) -> dict[str, object]:
        """Write operations go through individual services, not the gateway."""
        logger.debug("Create not supported in GCS read mode for '%s'", collection)
        return data

    def update(
        self, collection: str, _record_id: str, data: dict[str, object]
    ) -> dict[str, object] | None:
        """Write operations go through individual services, not the gateway."""
        logger.debug("Update not supported in GCS read mode for '%s'", collection)
        return data

    def delete(self, collection: str, _record_id: str) -> bool:
        """Write operations go through individual services, not the gateway."""
        logger.debug("Delete not supported in GCS read mode for '%s'", collection)
        return False

    def reset(self) -> None:
        """No-op in GCS mode."""


# Backward-compatible alias so existing imports still work
LiveDomainService = GcsDomainService
