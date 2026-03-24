"""Calendar domain seed data — economic results + corporate actions.

Mock data uses realistic Q1/Q2 2026 dates and values.
Seeded into collections:
    calendar_economic_results   — macro event results (NFP, CPI, FOMC, GDP, Claims, PCE)
    calendar_corporate_actions  — dividends, earnings, splits for common tickers
"""

from __future__ import annotations


def generate_economic_results() -> list[dict[str, object]]:
    """5 past released events + 4 upcoming events."""
    return [
        # Past — released with actual values
        {
            "id": "eco-nfp-2026-01",
            "event_type": "NFP",
            "release_date": "2026-01-10",
            "release_time_utc": "13:30",
            "actual_value": 256.0,
            "previous_value": 227.0,
            "unit": "thousands of persons",
            "status": "released",
        },
        {
            "id": "eco-cpi-2026-01",
            "event_type": "CPI",
            "release_date": "2026-01-15",
            "release_time_utc": "13:30",
            "actual_value": 316.8,
            "previous_value": 315.6,
            "unit": "index 1982-84=100",
            "status": "released",
        },
        {
            "id": "eco-fomc-2026-01",
            "event_type": "FOMC",
            "release_date": "2026-01-29",
            "release_time_utc": "19:00",
            "actual_value": 4.5,
            "previous_value": 4.5,
            "unit": "percent",
            "status": "released",
        },
        {
            "id": "eco-nfp-2026-02",
            "event_type": "NFP",
            "release_date": "2026-02-06",
            "release_time_utc": "13:30",
            "actual_value": 198.0,
            "previous_value": 256.0,
            "unit": "thousands of persons",
            "status": "released",
        },
        {
            "id": "eco-cpi-2026-02",
            "event_type": "CPI",
            "release_date": "2026-02-12",
            "release_time_utc": "13:30",
            "actual_value": 317.4,
            "previous_value": 316.8,
            "unit": "index 1982-84=100",
            "status": "released",
        },
        # Upcoming — no actual values yet
        {
            "id": "eco-nfp-2026-03",
            "event_type": "NFP",
            "release_date": "2026-03-06",
            "release_time_utc": "13:30",
            "actual_value": None,
            "previous_value": 198.0,
            "unit": "thousands of persons",
            "status": "upcoming",
        },
        {
            "id": "eco-fomc-2026-03",
            "event_type": "FOMC",
            "release_date": "2026-03-19",
            "release_time_utc": "19:00",
            "actual_value": None,
            "previous_value": 4.5,
            "unit": "percent",
            "status": "upcoming",
        },
        {
            "id": "eco-cpi-2026-03",
            "event_type": "CPI",
            "release_date": "2026-03-12",
            "release_time_utc": "13:30",
            "actual_value": None,
            "previous_value": 317.4,
            "unit": "index 1982-84=100",
            "status": "upcoming",
        },
        {
            "id": "eco-gdp-2026-q4",
            "event_type": "GDP",
            "release_date": "2026-03-27",
            "release_time_utc": "13:30",
            "actual_value": None,
            "previous_value": 28_400.0,
            "unit": "billions USD (annualised)",
            "status": "upcoming",
        },
    ]


def generate_corporate_actions() -> list[dict[str, object]]:
    """Dividends, earnings, splits for AAPL, MSFT, JPM, NVDA, SPY."""
    return [
        # AAPL — quarterly dividend
        {
            "id": "ca-aapl-div-2026-02",
            "ticker": "AAPL",
            "event_type": "dividend",
            "event_date": "2026-02-07",
            "amount": 0.25,
            "actual_eps": None,
            "estimated_eps": None,
            "status": "confirmed",
        },
        # AAPL — quarterly earnings (past)
        {
            "id": "ca-aapl-earn-2026-q1",
            "ticker": "AAPL",
            "event_type": "earnings",
            "event_date": "2026-01-30",
            "amount": None,
            "actual_eps": 2.40,
            "estimated_eps": 2.35,
            "status": "confirmed",
        },
        # MSFT — quarterly dividend
        {
            "id": "ca-msft-div-2026-02",
            "ticker": "MSFT",
            "event_type": "dividend",
            "event_date": "2026-02-20",
            "amount": 0.83,
            "actual_eps": None,
            "estimated_eps": None,
            "status": "confirmed",
        },
        # MSFT — upcoming earnings
        {
            "id": "ca-msft-earn-2026-q2",
            "ticker": "MSFT",
            "event_type": "earnings",
            "event_date": "2026-04-23",
            "amount": None,
            "actual_eps": None,
            "estimated_eps": 3.22,
            "status": "upcoming",
        },
        # JPM — upcoming dividend
        {
            "id": "ca-jpm-div-2026-04",
            "ticker": "JPM",
            "event_type": "dividend",
            "event_date": "2026-04-04",
            "amount": 1.25,
            "actual_eps": None,
            "estimated_eps": None,
            "status": "upcoming",
        },
        # JPM — recent earnings
        {
            "id": "ca-jpm-earn-2026-q1",
            "ticker": "JPM",
            "event_type": "earnings",
            "event_date": "2026-01-15",
            "amount": None,
            "actual_eps": 4.81,
            "estimated_eps": 4.52,
            "status": "confirmed",
        },
        # NVDA — upcoming earnings
        {
            "id": "ca-nvda-earn-2026-q4",
            "ticker": "NVDA",
            "event_type": "earnings",
            "event_date": "2026-04-09",
            "amount": None,
            "actual_eps": None,
            "estimated_eps": 0.89,
            "status": "upcoming",
        },
        # SPY — quarterly dividend
        {
            "id": "ca-spy-div-2026-03",
            "ticker": "SPY",
            "event_type": "dividend",
            "event_date": "2026-03-21",
            "amount": 1.88,
            "actual_eps": None,
            "estimated_eps": None,
            "status": "confirmed",
        },
    ]


def seed_calendar(store: object) -> None:
    """Seed calendar domain into MockStateStore."""
    from typing import Protocol

    class _Seedable(Protocol):
        def seed(self, collection: str, items: list[dict[str, object]]) -> None: ...

    _store: _Seedable = store  # type: ignore[assignment]
    _store.seed("calendar_economic_results", generate_economic_results())
    _store.seed("calendar_corporate_actions", generate_corporate_actions())
