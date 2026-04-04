"""Derivatives domain — options chain, vol surface, portfolio Greeks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import single_response
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/options-chain")
async def get_options_chain(
    request: Request,
    underlying: str = Query("BTC"),
    venue: str = Query("deribit"),
) -> dict[str, object]:
    """Get options chain for an underlying. Serves seeded data matching
    features-volatility-service output shapes."""
    service = get_service(request)
    records = service.list(
        "options_chain",
        filters={"underlying": underlying, "venue": venue},
    )
    return single_response(records, underlying=underlying, venue=venue)


@router.get("/vol-surface")
async def get_vol_surface(
    request: Request,
    underlying: str = Query("BTC"),
) -> dict[str, object]:
    """Get volatility surface. Serves seeded data matching
    features-volatility-service vol surface computation."""
    service = get_service(request)
    records = service.list("vol_surfaces", filters={"underlying": underlying})
    surface = records[0] if records else {}
    return single_response(surface, underlying=underlying)


@router.get("/portfolio-greeks")
async def get_portfolio_greeks(
    request: Request,
) -> dict[str, object]:
    """Get aggregated portfolio Greeks across options positions."""
    service = get_service(request)
    records = service.list("portfolio_greeks")
    if records:
        return single_response(records[0])
    return single_response(
        {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
        }
    )
