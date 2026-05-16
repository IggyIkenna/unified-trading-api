"""Events domain router — economic calendar, ML predictions, news feed, event positions.

Provides the event-driven macro dashboard data for the trading terminal UI.

Endpoints:
    GET /events/calendar     — upcoming economic events with countdown data
    GET /events/predictions  — ML-predicted market impact per event
    GET /events/news         — recent news and macro announcements
    GET /events/positions    — active positions taken on event signals

Mock mode: reads from MockStateStore (events_calendar, events_predictions,
events_news, events_positions).
Live mode: reads from GCS parquet output of features-calendar-service (deferred).
"""

# SCHEMA_PROVENANCE_EXEMPT: EconomicEventItem / EventImpactPredictionItem /
# EventPositionItem / NewsFeedItemModel / ScenarioModel are HTTP response DTOs
# that flatten domain records from economic-calendar-service + event-driven
# strategies into the shape the trading-terminal UI consumes. Underlying
# contracts live in UAC; this router maps them for the wire.

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    single_response,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ScenarioModel(BaseModel):  # CORRECT-LOCAL: API response model
    """Single conditional scenario for an event impact prediction."""

    label: str
    expected_move_pct: float
    probability: float


class EconomicEventItem(BaseModel):  # CORRECT-LOCAL: API response model
    """Single upcoming economic event with schedule and impact data."""

    id: str = ""
    name: str
    event_type: str  # FOMC | CPI | NFP | GDP | PCE | CLAIMS | ECB | BOJ | ISM
    scheduled_at: str  # ISO-8601
    impact: str  # HIGH | MEDIUM | LOW
    previous_value: str
    forecast: str
    actual_value: str | None = None
    currency: str = "USD"
    region: str = "US"


class EventImpactPredictionItem(BaseModel):  # CORRECT-LOCAL: API response model
    """ML-predicted market impact for a specific event-instrument pair."""

    id: str = ""
    event_id: str
    event_name: str
    instrument: str
    scenario_above: ScenarioModel
    scenario_below: ScenarioModel
    scenario_inline: ScenarioModel
    model_id: str
    confidence: float
    updated_at: str


class NewsFeedItemModel(BaseModel):  # CORRECT-LOCAL: API response model
    """Single news or macro announcement item."""

    id: str = ""
    title: str
    source: str
    published_at: str
    sentiment: str  # bullish | bearish | neutral
    category: str
    instruments: list[str] = []
    summary: str = ""


class EventPositionItem(BaseModel):  # CORRECT-LOCAL: API response model
    """Active position taken on an event signal."""

    id: str = ""
    event_id: str
    event_name: str
    instrument: str
    direction: str  # LONG | SHORT
    entry_price: float
    current_price: float
    size: float
    pnl_usd: float
    phase: str  # PRE_EVENT | POST_EVENT
    strategy_id: str = ""
    opened_at: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/calendar")
async def get_events_calendar(
    request: Request,
    impact: str | None = Query(None, description="Filter by impact level: HIGH | MEDIUM | LOW"),
    region: str | None = Query(None, description="Filter by region: US | EU | JP"),
) -> dict[str, object]:
    """Get upcoming economic events for the calendar view.

    Returns a list of EconomicEventItem records sorted by scheduled_at.

    Mock mode: seeded from seed_events.py.
    Live mode (future): reads from GCS calendar pipeline output.
    """
    service = get_service(request)
    records: list[dict[str, object]] = service.list("events_calendar")

    if impact:
        records = [r for r in records if str(r.get("impact", "")).upper() == impact.upper()]  # noqa: qg-empty-fallback

    if region:
        records = [r for r in records if str(r.get("region", "")).upper() == region.upper()]  # noqa: qg-empty-fallback

    return single_response(
        records,
        count=len(records),
        filters={"impact": impact, "region": region},
    )


@router.get("/predictions")
async def get_event_predictions(
    request: Request,
    event_id: str | None = Query(None, description="Filter predictions by event ID"),
    instrument: str | None = Query(None, description="Filter by instrument (e.g. BTC-USD)"),
) -> dict[str, object]:
    """Get ML-predicted market impact scenarios for upcoming events.

    Returns a list of EventImpactPredictionItem records with three conditional
    scenarios per event-instrument pair.

    Mock mode: seeded from seed_events.py.
    Live mode (future): reads from ML model inference output.
    """
    service = get_service(request)
    records: list[dict[str, object]] = service.list("events_predictions")

    if event_id:
        records = [r for r in records if r.get("event_id") == event_id]

    if instrument:
        records = [r for r in records if str(r.get("instrument", "")).upper() == instrument.upper()]  # noqa: qg-empty-fallback

    return single_response(
        records,
        count=len(records),
        filters={"event_id": event_id, "instrument": instrument},
    )


@router.get("/news")
async def get_events_news(
    request: Request,
    sentiment: str | None = Query(None, description="Filter by sentiment: bullish | bearish | neutral"),
    category: str | None = Query(None, description="Filter by category (e.g. macro, on-chain, governance)"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
) -> dict[str, object]:
    """Get recent news feed items and macro announcements.

    Returns a list of NewsFeedItemModel records sorted by published_at descending.

    Mock mode: seeded from seed_events.py.
    Live mode (future): reads from news aggregation pipeline.
    """
    service = get_service(request)
    records: list[dict[str, object]] = service.list("events_news")

    if sentiment:
        records = [r for r in records if str(r.get("sentiment", "")).lower() == sentiment.lower()]  # noqa: qg-empty-fallback

    if category:
        records = [r for r in records if str(r.get("category", "")).lower() == category.lower()]  # noqa: qg-empty-fallback

    records = records[:limit]

    return single_response(
        records,
        count=len(records),
        filters={"sentiment": sentiment, "category": category, "limit": limit},
    )


@router.get("/positions")
async def get_event_positions(
    request: Request,
    phase: str | None = Query(None, description="Filter by phase: PRE_EVENT | POST_EVENT"),
    event_id: str | None = Query(None, description="Filter positions by event ID"),
) -> dict[str, object]:
    """Get active positions taken based on event signals.

    Returns a list of EventPositionItem records with P&L and phase data.

    Mock mode: seeded from seed_events.py.
    Live mode (future): reads from execution-service event position state.
    """
    service = get_service(request)
    records: list[dict[str, object]] = service.list("events_positions")

    if phase:
        records = [r for r in records if str(r.get("phase", "")).upper() == phase.upper()]  # noqa: qg-empty-fallback

    if event_id:
        records = [r for r in records if r.get("event_id") == event_id]

    return single_response(
        records,
        count=len(records),
        filters={"phase": phase, "event_id": event_id},
    )
