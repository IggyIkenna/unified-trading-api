"""DeFi LP (Liquidity Provider) domain — active MM / LP rebalancing endpoints."""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, Request

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    single_response,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _tick_to_price(tick: int) -> float:
    """Uniswap V3 tick to price (simplified)."""
    return math.pow(1.0001, tick)


@router.get("/position-range")
async def get_position_range(request: Request) -> dict[str, object]:
    """Get current LP position range and price data."""
    service = get_service(request)
    records = service.list("defi_lp_position_range")
    if records:
        return single_response(records[0])
    # Fallback mock for when seed data is missing
    return single_response(
        {
            "pool": "ETH/USDC",
            "venue_id": "UNISWAPV3-ETHEREUM",
            "token0": "ETH",
            "token1": "USDC",
            "fee_tier": 0.05,
            "current_tick": 200500,
            "tick_lower": 195000,
            "tick_upper": 205000,
            "current_price": _tick_to_price(200500),
            "price_lower": _tick_to_price(195000),
            "price_upper": _tick_to_price(205000),
            "position_value_usd": 250000,
            "range_utilization": 0.55,
            "near_edge_warning": False,
        }
    )


@router.get("/impermanent-loss")
async def get_impermanent_loss(request: Request) -> dict[str, object]:
    """Get impermanent loss time series (LP value vs HODL)."""
    service = get_service(request)
    records = service.list("defi_lp_impermanent_loss")
    return single_response(records)


@router.get("/rebalance-history")
async def get_rebalance_history(request: Request) -> dict[str, object]:
    """Get LP rebalance event history."""
    service = get_service(request)
    records = service.list("defi_lp_rebalance_history")
    return single_response(records)


@router.get("/ml-confidence")
async def get_ml_confidence(request: Request) -> dict[str, object]:
    """Get current ML rebalance confidence and recommendation."""
    service = get_service(request)
    records = service.list("defi_lp_ml_confidence")
    if records:
        return single_response(records[0])
    return single_response(
        {
            "recommended_action": "HOLD",
            "confidence": 0.43,
            "hold_threshold": 0.65,
            "top_features": [
                {"name": "price_vs_range_center", "importance": 0.31},
                {"name": "realized_vol_4h", "importance": 0.24},
                {"name": "fee_accumulation_rate", "importance": 0.19},
                {"name": "gas_price_gwei", "importance": 0.14},
                {"name": "time_since_last_rebalance", "importance": 0.12},
            ],
            "model_version": "lp-rebal-v2.3.1",
        }
    )


@router.get("/fee-revenue")
async def get_fee_revenue(request: Request) -> dict[str, object]:
    """Get LP fee revenue accumulation (24h/7d/30d)."""
    service = get_service(request)
    records = service.list("defi_lp_fee_revenue")
    if records:
        return single_response(records[0])
    return single_response(
        {
            "fees_24h_usd": 142.50,
            "fees_7d_usd": 987.30,
            "fees_30d_usd": 4125.00,
            "fee_apr_7d": 20.6,
            "fee_yield_30d_pct": 1.65,
            "token0_fees": 0.0412,
            "token1_fees": 71.25,
            "token0_symbol": "ETH",
            "token1_symbol": "USDC",
        }
    )
