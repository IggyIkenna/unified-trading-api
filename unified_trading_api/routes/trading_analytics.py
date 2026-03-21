"""Trading analytics domain — PnL, timeseries, performance, organizations, settlements, instruments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


# ── GET endpoints ──────────────────────────────────────────────


@router.get("/pnl")
async def get_pnl(
    request: Request,
    venue: str = Query(None),
    period: str = Query("1d"),
) -> dict[str, object]:
    """Get PnL breakdown."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("pnl")
        if venue:
            records = [r for r in records if r.get("venue") == venue]
        return {"period": period, "pnl": records}
    return {"error": "real mode not yet wired"}


@router.get("/timeseries")
async def get_timeseries(
    request: Request,
    metric: str = Query("equity"),
    period: str = Query("1d"),
    granularity: str = Query("1h"),
) -> dict[str, object]:
    """Get analytics timeseries data."""
    if getattr(request.app.state, "mock_mode", True):
        return {
            "metric": metric,
            "period": period,
            "granularity": granularity,
            "series": mock_store.list("analytics_timeseries"),
        }
    return {"error": "real mode not yet wired"}


@router.get("/performance")
async def get_performance(
    request: Request,
    period: str = Query("30d"),
) -> dict[str, object]:
    """Get performance metrics."""
    if getattr(request.app.state, "mock_mode", True):
        return {"period": period, "performance": mock_store.list("performance")}
    return {"error": "real mode not yet wired"}


@router.get("/organizations")
async def get_organizations(
    request: Request,
) -> dict[str, object]:
    """Get analytics organizations."""
    if getattr(request.app.state, "mock_mode", True):
        return {"organizations": mock_store.list("analytics_organizations")}
    return {"error": "real mode not yet wired"}


@router.get("/settlements")
async def get_settlements(
    request: Request,
    status: str = Query(None),
    limit: int = Query(50),
) -> dict[str, object]:
    """Get settlement records."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("settlements")
        if status:
            records = [r for r in records if r.get("status") == status]
        return {"settlements": records[:limit]}
    return {"error": "real mode not yet wired"}


@router.get("/instruments")
async def get_instruments(
    request: Request,
    asset_class: str = Query(None),
) -> dict[str, object]:
    """Get analytics instrument list."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("analytics_instruments")
        if asset_class:
            records = [r for r in records if r.get("asset_class") == asset_class]
        return {"instruments": records}
    return {"error": "real mode not yet wired"}


# ── POST endpoints ─────────────────────────────────────────────


@router.post("/pnl")
async def create_pnl_snapshot(
    request: Request,
) -> dict[str, object]:
    """Trigger a PnL snapshot calculation."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        mock_store.add("pnl", body)
        return {"status": "created", "record": body}
    return {"error": "real mode not yet wired"}


@router.post("/timeseries")
async def create_timeseries_entry(
    request: Request,
) -> dict[str, object]:
    """Add a timeseries data point."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        mock_store.add("analytics_timeseries", body)
        return {"status": "created", "record": body}
    return {"error": "real mode not yet wired"}


@router.post("/performance")
async def create_performance_snapshot(
    request: Request,
) -> dict[str, object]:
    """Trigger a performance snapshot."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        mock_store.add("performance", body)
        return {"status": "created", "record": body}
    return {"error": "real mode not yet wired"}


@router.post("/settlements")
async def create_settlement(
    request: Request,
) -> dict[str, object]:
    """Create a settlement record."""
    if getattr(request.app.state, "mock_mode", True):
        body = await request.json()
        mock_store.add("settlements", body)
        return {"status": "created", "record": body}
    return {"error": "real mode not yet wired"}
