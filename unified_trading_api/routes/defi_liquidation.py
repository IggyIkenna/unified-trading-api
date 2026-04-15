"""DeFi Liquidation Monitoring — risk heatmap, cascade risk, events, captured positions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import single_response
from unified_trading_api.services.factory import get_service

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/risk-heatmap")
async def get_risk_heatmap(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    as_of: str = Query(None, description="Reconciliation date for batch mode"),
) -> dict[str, object]:
    """Get liquidation risk heatmap — positions by asset x health factor range."""
    service = get_service(request)
    data = service.get("liquidation_risk_heatmap", filters={"as_of": as_of})
    return single_response(data, mode=mode, as_of=as_of)


@router.get("/cascade-risk")
async def get_cascade_risk(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    as_of: str = Query(None, description="Reconciliation date for batch mode"),
) -> dict[str, object]:
    """Get current cascade risk indicator — correlated liquidation cluster analysis."""
    service = get_service(request)
    data = service.get("cascade_risk", filters={"as_of": as_of})
    return single_response(data, mode=mode, as_of=as_of)


@router.get("/events")
async def get_liquidation_events(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    protocol: str = Query(None, description="Filter by protocol (e.g. AAVE_V3)"),
    chain: str = Query(None, description="Filter by chain (e.g. ETHEREUM)"),
    as_of: str = Query(None, description="Reconciliation date for batch mode"),
) -> dict[str, object]:
    """Get recent on-chain liquidation events."""
    service = get_service(request)
    data = service.list(
        "liquidation_events",
        filters={"protocol": protocol, "chain": chain, "as_of": as_of},
    )
    return single_response(data, mode=mode, as_of=as_of)


@router.get("/captured-positions")
async def get_captured_positions(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
    status: str = Query(None, description="Filter by status (ACTIVE, CLOSED, PENDING_EXIT)"),
    as_of: str = Query(None, description="Reconciliation date for batch mode"),
) -> dict[str, object]:
    """Get captured positions from liquidation sniping."""
    service = get_service(request)
    data = service.list(
        "captured_positions",
        filters={"status": status, "as_of": as_of},
    )
    return single_response(data, mode=mode, as_of=as_of)
