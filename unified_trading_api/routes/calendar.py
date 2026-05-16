"""Calendar domain router.

Exposes economic results (NFP, CPI, FOMC, GDP, Claims, PCE) and corporate actions
(dividends, earnings, splits) for display in the trading terminal UI.

Endpoints:
    GET /calendar/economic-results   — macro event actuals + upcoming schedule
    GET /calendar/corporate-actions  — dividends, earnings, splits per ticker

Mock mode: reads from MockStateStore (calendar_economic_results, calendar_corporate_actions).
Live mode: reads from GCS parquet output of features-calendar-service (deferred).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    single_response,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/economic-results")
async def get_economic_results(
    request: Request,
    days_back: int = Query(30, ge=1, le=365, description="Days of history to return"),
    event_types: str | None = Query(None, description="Comma-separated event types to filter (e.g. NFP,CPI,FOMC)"),
) -> dict[str, object]:
    """Get recent and upcoming macro economic event results.

    Returns a list of EconomicResultItem records. Past events include actual_value;
    upcoming events have actual_value=null.

    Mock mode: seeded from seed_calendar.py (realistic Q1/Q2 2026 data).
    Live mode (future): reads from GCS calendar/economic_results/by_date/ parquet.
    """
    service = get_service(request)
    records: list[dict[str, object]] = service.list("calendar_economic_results")

    # Apply event_types filter if provided
    if event_types:
        allowed = {t.strip().upper() for t in event_types.split(",")}
        records = [r for r in records if str(r.get("event_type", "")).upper() in allowed]

    return single_response(
        records,
        count=len(records),
        filters={"days_back": days_back, "event_types": event_types},
    )


@router.get("/corporate-actions")
async def get_corporate_actions(
    request: Request,
    tickers: str | None = Query(None, description="Comma-separated tickers to filter (e.g. AAPL,MSFT)"),
    event_type: str | None = Query(None, description="Filter by event type: dividend | earnings | split"),
    days_forward: int = Query(30, ge=1, le=365, description="Days forward to include upcoming events"),
) -> dict[str, object]:
    """Get corporate actions calendar — dividends, earnings, splits.

    Returns a list of CorporateActionItem records. Confirmed events include actual data;
    upcoming events may have estimated_eps but no actual_eps.

    Mock mode: seeded from seed_calendar.py (AAPL, MSFT, JPM, NVDA, SPY).
    Live mode (future): reads from GCS calendar/corporate_actions/by_date/ parquet.
    """
    service = get_service(request)
    records: list[dict[str, object]] = service.list("calendar_corporate_actions")

    # Apply ticker filter
    if tickers:
        allowed_tickers = {t.strip().upper() for t in tickers.split(",")}
        records = [r for r in records if str(r.get("ticker", "")).upper() in allowed_tickers]

    # Apply event_type filter
    if event_type:
        records = [r for r in records if r.get("event_type") == event_type.lower()]

    return single_response(
        records,
        count=len(records),
        filters={"tickers": tickers, "event_type": event_type, "days_forward": days_forward},
    )
