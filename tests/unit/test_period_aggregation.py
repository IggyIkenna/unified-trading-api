"""Tests for period aggregation utilities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from unified_trading_api.services.period_aggregation import (
    compute_multi_period_summary,
    compute_period_changes,
    resolve_period_start,
)

# ---------------------------------------------------------------------------
# resolve_period_start
# ---------------------------------------------------------------------------


class TestResolvePeriodStart:
    """Tests for resolve_period_start()."""

    def test_1d_returns_yesterday(self) -> None:
        result = resolve_period_start("1d", as_of=date(2026, 3, 15))
        assert result == date(2026, 3, 14)

    def test_wtd_returns_monday_of_current_week(self) -> None:
        # 2026-03-15 is a Sunday → Monday is 2026-03-09
        result = resolve_period_start("wtd", as_of=date(2026, 3, 15))
        assert result == date(2026, 3, 9)

    def test_wtd_on_monday_returns_same_day(self) -> None:
        # 2026-03-09 is a Monday
        result = resolve_period_start("wtd", as_of=date(2026, 3, 9))
        assert result == date(2026, 3, 9)

    def test_mtd_returns_first_of_month(self) -> None:
        result = resolve_period_start("mtd", as_of=date(2026, 3, 15))
        assert result == date(2026, 3, 1)

    def test_qtd_q1_returns_jan1(self) -> None:
        result = resolve_period_start("qtd", as_of=date(2026, 2, 20))
        assert result == date(2026, 1, 1)

    def test_qtd_q2_returns_apr1(self) -> None:
        result = resolve_period_start("qtd", as_of=date(2026, 5, 10))
        assert result == date(2026, 4, 1)

    def test_qtd_q3_returns_jul1(self) -> None:
        result = resolve_period_start("qtd", as_of=date(2026, 8, 15))
        assert result == date(2026, 7, 1)

    def test_qtd_q4_returns_oct1(self) -> None:
        result = resolve_period_start("qtd", as_of=date(2026, 11, 30))
        assert result == date(2026, 10, 1)

    def test_ytd_returns_jan1(self) -> None:
        result = resolve_period_start("ytd", as_of=date(2026, 3, 15))
        assert result == date(2026, 1, 1)

    def test_7d_returns_7_days_ago(self) -> None:
        result = resolve_period_start("7d", as_of=date(2026, 3, 15))
        assert result == date(2026, 3, 8)

    def test_30d_returns_30_days_ago(self) -> None:
        result = resolve_period_start("30d", as_of=date(2026, 3, 15))
        assert result == date(2026, 2, 13)

    def test_90d_rolling(self) -> None:
        result = resolve_period_start("90d", as_of=date(2026, 3, 15))
        assert result == date(2025, 12, 15)

    def test_365d_rolling(self) -> None:
        result = resolve_period_start("365d", as_of=date(2026, 3, 15))
        assert result == date(2025, 3, 15)

    def test_custom_as_of_mtd(self) -> None:
        result = resolve_period_start("mtd", as_of=date(2026, 3, 15))
        assert result == date(2026, 3, 1)

    def test_unknown_period_defaults_to_1d(self) -> None:
        result = resolve_period_start("garbage", as_of=date(2026, 3, 15))
        assert result == date(2026, 3, 14)

    def test_unknown_period_non_numeric_d(self) -> None:
        result = resolve_period_start("abcd", as_of=date(2026, 3, 15))
        assert result == date(2026, 3, 14)


# ---------------------------------------------------------------------------
# compute_period_changes
# ---------------------------------------------------------------------------


def _make_snapshot(dt: date, **fields: str) -> dict[str, object]:
    """Helper to build a snapshot dict."""
    snap: dict[str, object] = {"date": dt.isoformat()}
    snap.update(fields)
    return snap


class TestComputePeriodChanges:
    """Tests for compute_period_changes()."""

    def test_basic_two_snapshots(self) -> None:
        snapshots = [
            _make_snapshot(date(2026, 3, 14), pnl="1000"),
            _make_snapshot(date(2026, 3, 15), pnl="1200"),
        ]
        result = compute_period_changes(snapshots, "1d", ["pnl"], as_of=date(2026, 3, 15))
        assert result["period"] == "1d"
        assert result["start_date"] == "2026-03-14"
        assert result["end_date"] == "2026-03-15"
        assert Decimal(str(result["changes"]["pnl"])) == Decimal("200")
        assert Decimal(str(result["changes_pct"]["pnl"])) == Decimal("20")

    def test_multiple_numeric_fields(self) -> None:
        snapshots = [
            _make_snapshot(date(2026, 3, 14), pnl="1000", nav="50000"),
            _make_snapshot(date(2026, 3, 15), pnl="1200", nav="51000"),
        ]
        result = compute_period_changes(snapshots, "1d", ["pnl", "nav"], as_of=date(2026, 3, 15))
        assert Decimal(str(result["changes"]["pnl"])) == Decimal("200")
        assert Decimal(str(result["changes"]["nav"])) == Decimal("1000")
        assert Decimal(str(result["changes_pct"]["nav"])) == Decimal("2")

    def test_missing_start_snapshot_falls_back(self) -> None:
        # Period start is 2026-03-14 but no snapshot for that date;
        # closest backward is 2026-03-13.
        snapshots = [
            _make_snapshot(date(2026, 3, 13), pnl="900"),
            _make_snapshot(date(2026, 3, 15), pnl="1200"),
        ]
        result = compute_period_changes(snapshots, "1d", ["pnl"], as_of=date(2026, 3, 15))
        # Start fell back to 2026-03-13 (900), end is 1200 → delta 300
        assert result["changes"]["pnl"] == str(Decimal("300"))

    def test_missing_end_snapshot_falls_back(self) -> None:
        # as_of is 2026-03-15 but no snapshot for that date;
        # closest backward is 2026-03-14.
        snapshots = [
            _make_snapshot(date(2026, 3, 14), pnl="1000"),
        ]
        result = compute_period_changes(snapshots, "1d", ["pnl"], as_of=date(2026, 3, 15))
        # Both start and end resolve to 2026-03-14 → delta 0
        assert result["changes"]["pnl"] == str(Decimal("0"))

    def test_zero_start_value_pct_is_none(self) -> None:
        snapshots = [
            _make_snapshot(date(2026, 3, 14), pnl="0"),
            _make_snapshot(date(2026, 3, 15), pnl="500"),
        ]
        result = compute_period_changes(snapshots, "1d", ["pnl"], as_of=date(2026, 3, 15))
        assert result["changes"]["pnl"] == str(Decimal("500"))
        assert result["changes_pct"]["pnl"] is None

    def test_negative_change(self) -> None:
        snapshots = [
            _make_snapshot(date(2026, 3, 14), pnl="1000"),
            _make_snapshot(date(2026, 3, 15), pnl="800"),
        ]
        result = compute_period_changes(snapshots, "1d", ["pnl"], as_of=date(2026, 3, 15))
        assert Decimal(str(result["changes"]["pnl"])) == Decimal("-200")
        # -200 / |1000| * 100 = -20
        assert Decimal(str(result["changes_pct"]["pnl"])) == Decimal("-20")

    def test_empty_snapshot_list(self) -> None:
        result = compute_period_changes([], "1d", ["pnl"], as_of=date(2026, 3, 15))
        # No snapshots → both start and end are None → values default to 0
        assert result["changes"]["pnl"] == str(Decimal("0"))
        assert result["changes_pct"]["pnl"] is None

    def test_negative_start_value_pct_uses_abs(self) -> None:
        snapshots = [
            _make_snapshot(date(2026, 3, 14), pnl="-200"),
            _make_snapshot(date(2026, 3, 15), pnl="100"),
        ]
        result = compute_period_changes(snapshots, "1d", ["pnl"], as_of=date(2026, 3, 15))
        # delta = 300, pct = 300 / |-200| * 100 = 150
        assert Decimal(str(result["changes"]["pnl"])) == Decimal("300")
        assert Decimal(str(result["changes_pct"]["pnl"])) == Decimal("150")

    def test_mtd_period_selects_correct_start(self) -> None:
        snapshots = [
            _make_snapshot(date(2026, 3, 1), pnl="5000"),
            _make_snapshot(date(2026, 3, 8), pnl="5500"),
            _make_snapshot(date(2026, 3, 15), pnl="6000"),
        ]
        result = compute_period_changes(snapshots, "mtd", ["pnl"], as_of=date(2026, 3, 15))
        assert result["start_date"] == "2026-03-01"
        assert result["end_date"] == "2026-03-15"
        assert result["changes"]["pnl"] == str(Decimal("1000"))


# ---------------------------------------------------------------------------
# compute_multi_period_summary
# ---------------------------------------------------------------------------


class TestComputeMultiPeriodSummary:
    """Tests for compute_multi_period_summary()."""

    def _build_daily_snapshots(self) -> list[dict[str, object]]:
        """Build snapshots covering a wide date range for multi-period tests."""
        ref = date(2026, 3, 15)
        snapshots: list[dict[str, object]] = []
        # Generate daily snapshots from 2025-01-01 to 2026-03-15
        # with a simple linear pnl series (day index * 10)
        start = date(2025, 1, 1)
        day_idx = 0
        current = start
        while current <= ref:
            snapshots.append(_make_snapshot(current, pnl=str(day_idx * 10)))
            current = date.fromordinal(current.toordinal() + 1)
            day_idx += 1
        return snapshots

    def test_returns_all_5_default_periods(self) -> None:
        snapshots = self._build_daily_snapshots()
        result = compute_multi_period_summary(snapshots, ["pnl"], as_of=date(2026, 3, 15))
        assert set(result.keys()) == {"1d", "wtd", "mtd", "qtd", "ytd"}

    def test_custom_period_list(self) -> None:
        snapshots = self._build_daily_snapshots()
        result = compute_multi_period_summary(
            snapshots,
            ["pnl"],
            periods=["7d", "30d"],
            as_of=date(2026, 3, 15),
        )
        assert set(result.keys()) == {"7d", "30d"}

    def test_consistent_with_compute_period_changes(self) -> None:
        snapshots = self._build_daily_snapshots()
        as_of = date(2026, 3, 15)
        multi = compute_multi_period_summary(snapshots, ["pnl"], as_of=as_of)
        for period_code in ["1d", "wtd", "mtd", "qtd", "ytd"]:
            single = compute_period_changes(snapshots, period_code, ["pnl"], as_of=as_of)
            assert multi[period_code] == single, f"Mismatch for period {period_code}"

    def test_each_period_has_correct_start_date(self) -> None:
        snapshots = self._build_daily_snapshots()
        result = compute_multi_period_summary(snapshots, ["pnl"], as_of=date(2026, 3, 15))
        assert result["1d"]["start_date"] == "2026-03-14"
        assert result["mtd"]["start_date"] == "2026-03-01"
        assert result["qtd"]["start_date"] == "2026-01-01"
        assert result["ytd"]["start_date"] == "2026-01-01"
        # 2026-03-15 is Sunday → Monday = 2026-03-09
        assert result["wtd"]["start_date"] == "2026-03-09"
