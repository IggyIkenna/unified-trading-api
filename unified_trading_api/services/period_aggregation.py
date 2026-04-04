"""Period aggregation utilities — day-over-day, MTD, rolling, arbitrary date ranges.

Computes temporal changes from daily snapshot data. All timestamps are UTC.
Used by trading API routes to serve period-based P&L, risk, positions, and
exposure data to the UI.

Snapshot format: each snapshot is a dict with at least:
  - "date": ISO date string (YYYY-MM-DD)
  - numeric fields (Decimal or float) that can be differenced

Period types:
  - "1d": Day-over-day (today vs yesterday)
  - "wtd": Week-to-date (today vs last Monday 00:00 UTC)
  - "mtd": Month-to-date (today vs 1st of month 00:00 UTC)
  - "qtd": Quarter-to-date (today vs 1st of quarter 00:00 UTC)
  - "ytd": Year-to-date (today vs Jan 1 00:00 UTC)
  - "7d", "30d", "90d", "365d": Rolling N-day windows
  - "custom": Arbitrary start/end dates
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


def resolve_period_start(period: str, as_of: date | None = None) -> date:
    """Resolve a period code to the start date (UTC midnight).

    Args:
        period: Period code (1d, wtd, mtd, qtd, ytd, 7d, 30d, 90d, 365d).
        as_of: Reference date. Defaults to today UTC.

    Returns:
        Start date for the period.
    """
    ref = as_of or datetime.now(UTC).date()

    if period == "1d":
        return ref - timedelta(days=1)
    if period == "wtd":
        # Monday of current week (ISO weekday: Monday=1)
        return ref - timedelta(days=ref.weekday())
    if period == "mtd":
        return ref.replace(day=1)
    if period == "qtd":
        quarter_month = ((ref.month - 1) // 3) * 3 + 1
        return ref.replace(month=quarter_month, day=1)
    if period == "ytd":
        return ref.replace(month=1, day=1)

    # Rolling N-day: "7d", "30d", "90d", "365d"
    if period.endswith("d") and period[:-1].isdigit():
        days = int(period[:-1])
        return ref - timedelta(days=days)

    logger.warning("Unknown period code %r — defaulting to 1d", period)
    return ref - timedelta(days=1)


def compute_period_changes(
    snapshots: list[dict[str, object]],
    period: str,
    numeric_fields: list[str],
    *,
    as_of: date | None = None,
    date_field: str = "date",
) -> dict[str, object]:
    """Compute changes between period start and end from daily snapshots.

    Args:
        snapshots: List of daily snapshot dicts, each with a date field and numeric fields.
        period: Period code (1d, mtd, 7d, etc.).
        numeric_fields: Names of fields to compute deltas for.
        as_of: Reference end date. Defaults to today UTC.
        date_field: Key in snapshot dict containing the ISO date string.

    Returns:
        Dict with:
          - period: the period code
          - start_date: ISO date string of period start
          - end_date: ISO date string of period end (as_of)
          - start_values: {field: value} at period start
          - end_values: {field: value} at period end
          - changes: {field: end - start} absolute change
          - changes_pct: {field: (end - start) / |start| * 100} percentage change
    """
    ref = as_of or datetime.now(UTC).date()
    period_start = resolve_period_start(period, ref)

    # Index snapshots by date string
    by_date: dict[str, dict[str, object]] = {}
    for snap in snapshots:
        d = str(snap.get(date_field, ""))
        if d:
            by_date[d] = snap

    start_key = period_start.isoformat()
    end_key = ref.isoformat()

    # Find closest available snapshot if exact date missing
    start_snap = by_date.get(start_key)
    end_snap = by_date.get(end_key)

    if start_snap is None:
        start_snap = _find_closest_snapshot(by_date, period_start, direction="backward")
    if end_snap is None:
        end_snap = _find_closest_snapshot(by_date, ref, direction="backward")

    start_values: dict[str, Decimal] = {}
    end_values: dict[str, Decimal] = {}
    changes: dict[str, Decimal] = {}
    changes_pct: dict[str, Decimal | None] = {}

    for field in numeric_fields:
        sv = _to_decimal(start_snap.get(field) if start_snap else None)
        ev = _to_decimal(end_snap.get(field) if end_snap else None)
        start_values[field] = sv
        end_values[field] = ev
        delta = ev - sv
        changes[field] = delta
        if sv != Decimal("0"):
            changes_pct[field] = (delta / abs(sv)) * Decimal("100")
        else:
            changes_pct[field] = None

    return {
        "period": period,
        "start_date": start_key,
        "end_date": end_key,
        "start_values": {k: str(v) for k, v in start_values.items()},
        "end_values": {k: str(v) for k, v in end_values.items()},
        "changes": {k: str(v) for k, v in changes.items()},
        "changes_pct": {k: str(v) if v is not None else None for k, v in changes_pct.items()},
    }


def compute_multi_period_summary(
    snapshots: list[dict[str, object]],
    numeric_fields: list[str],
    *,
    periods: list[str] | None = None,
    as_of: date | None = None,
    date_field: str = "date",
) -> dict[str, dict[str, object]]:
    """Compute changes for multiple periods at once.

    Args:
        snapshots: Daily snapshot dicts.
        numeric_fields: Fields to compute deltas for.
        periods: Period codes. Defaults to ["1d", "wtd", "mtd", "qtd", "ytd"].
        as_of: Reference end date.
        date_field: Key containing the date.

    Returns:
        Dict mapping period code → period change result.
    """
    if periods is None:
        periods = ["1d", "wtd", "mtd", "qtd", "ytd"]

    return {
        p: compute_period_changes(snapshots, p, numeric_fields, as_of=as_of, date_field=date_field)
        for p in periods
    }


def _find_closest_snapshot(
    by_date: dict[str, dict[str, object]],
    target: date,
    direction: str = "backward",
    max_days: int = 7,
) -> dict[str, object] | None:
    """Find the closest snapshot to a target date within max_days."""
    for offset in range(1, max_days + 1):
        if direction == "backward":
            candidate = (target - timedelta(days=offset)).isoformat()
        else:
            candidate = (target + timedelta(days=offset)).isoformat()
        if candidate in by_date:
            return by_date[candidate]
    return None


def _to_decimal(value: object) -> Decimal:
    """Convert a value to Decimal, defaulting to 0."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))
