"""DeFi Lending domain -- protocol APY comparison, arb positions, rate impact simulation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginated_response, single_response

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

# ---------------------------------------------------------------------------
# Seed data (mock mode) — realistic cross-protocol lending rates
# ---------------------------------------------------------------------------

_SEED_RATES: list[dict[str, object]] = [
    # Aave V3
    {
        "protocol": "Aave V3",
        "venue_id": "AAVEV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "USDC",
        "supply_apy_pct": 4.2,
        "borrow_apy_pct": 5.8,
        "spread_bps": 160,
        "utilization_pct": 82.1,
        "tvl_usd": 8_200_000_000,
    },
    {
        "protocol": "Aave V3",
        "venue_id": "AAVEV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "USDT",
        "supply_apy_pct": 4.0,
        "borrow_apy_pct": 5.5,
        "spread_bps": 150,
        "utilization_pct": 79.4,
        "tvl_usd": 5_100_000_000,
    },
    {
        "protocol": "Aave V3",
        "venue_id": "AAVEV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "WETH",
        "supply_apy_pct": 1.8,
        "borrow_apy_pct": 2.9,
        "spread_bps": 110,
        "utilization_pct": 65.2,
        "tvl_usd": 12_400_000_000,
    },
    {
        "protocol": "Aave V3",
        "venue_id": "AAVEV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "DAI",
        "supply_apy_pct": 3.9,
        "borrow_apy_pct": 5.3,
        "spread_bps": 140,
        "utilization_pct": 76.8,
        "tvl_usd": 2_800_000_000,
    },
    # Morpho Blue
    {
        "protocol": "Morpho Blue",
        "venue_id": "MORPHO-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "USDC",
        "supply_apy_pct": 5.1,
        "borrow_apy_pct": 6.4,
        "spread_bps": 130,
        "utilization_pct": 88.3,
        "tvl_usd": 1_900_000_000,
    },
    {
        "protocol": "Morpho Blue",
        "venue_id": "MORPHO-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "USDT",
        "supply_apy_pct": 4.8,
        "borrow_apy_pct": 6.1,
        "spread_bps": 130,
        "utilization_pct": 85.7,
        "tvl_usd": 1_200_000_000,
    },
    {
        "protocol": "Morpho Blue",
        "venue_id": "MORPHO-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "WETH",
        "supply_apy_pct": 2.3,
        "borrow_apy_pct": 3.5,
        "spread_bps": 120,
        "utilization_pct": 71.0,
        "tvl_usd": 2_100_000_000,
    },
    {
        "protocol": "Morpho Blue",
        "venue_id": "MORPHO-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "DAI",
        "supply_apy_pct": 4.6,
        "borrow_apy_pct": 5.9,
        "spread_bps": 130,
        "utilization_pct": 83.2,
        "tvl_usd": 800_000_000,
    },
    # Compound V3
    {
        "protocol": "Compound V3",
        "venue_id": "COMPOUNDV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "USDC",
        "supply_apy_pct": 3.8,
        "borrow_apy_pct": 5.2,
        "spread_bps": 140,
        "utilization_pct": 74.5,
        "tvl_usd": 3_400_000_000,
    },
    {
        "protocol": "Compound V3",
        "venue_id": "COMPOUNDV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "USDT",
        "supply_apy_pct": 3.5,
        "borrow_apy_pct": 4.9,
        "spread_bps": 140,
        "utilization_pct": 71.2,
        "tvl_usd": 1_800_000_000,
    },
    {
        "protocol": "Compound V3",
        "venue_id": "COMPOUNDV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "WETH",
        "supply_apy_pct": 1.5,
        "borrow_apy_pct": 2.6,
        "spread_bps": 110,
        "utilization_pct": 58.9,
        "tvl_usd": 4_600_000_000,
    },
    {
        "protocol": "Compound V3",
        "venue_id": "COMPOUNDV3-ETHEREUM",
        "chain": "ETHEREUM",
        "token": "DAI",
        "supply_apy_pct": 3.4,
        "borrow_apy_pct": 4.7,
        "spread_bps": 130,
        "utilization_pct": 69.3,
        "tvl_usd": 1_100_000_000,
    },
]

_SEED_POSITIONS: list[dict[str, object]] = [
    {
        "id": "pos-la-001",
        "borrow_protocol": "Compound V3",
        "borrow_venue_id": "COMPOUNDV3-ETHEREUM",
        "lend_protocol": "Morpho Blue",
        "lend_venue_id": "MORPHO-ETHEREUM",
        "token": "USDC",
        "chain": "ETHEREUM",
        "notional_usd": 2_500_000,
        "spread_captured_bps": 130,
        "health_factor": 2.45,
        "opened_at": "2026-04-10T14:30:00Z",
        "status": "active",
    },
    {
        "id": "pos-la-002",
        "borrow_protocol": "Compound V3",
        "borrow_venue_id": "COMPOUNDV3-ETHEREUM",
        "lend_protocol": "Morpho Blue",
        "lend_venue_id": "MORPHO-ETHEREUM",
        "token": "USDT",
        "chain": "ETHEREUM",
        "notional_usd": 1_800_000,
        "spread_captured_bps": 130,
        "health_factor": 2.31,
        "opened_at": "2026-04-11T09:15:00Z",
        "status": "active",
    },
    {
        "id": "pos-la-003",
        "borrow_protocol": "Aave V3",
        "borrow_venue_id": "AAVEV3-ETHEREUM",
        "lend_protocol": "Morpho Blue",
        "lend_venue_id": "MORPHO-ETHEREUM",
        "token": "WETH",
        "chain": "ETHEREUM",
        "notional_usd": 5_000_000,
        "spread_captured_bps": 50,
        "health_factor": 1.62,
        "opened_at": "2026-04-08T11:00:00Z",
        "status": "warning",
    },
    {
        "id": "pos-la-004",
        "borrow_protocol": "Compound V3",
        "borrow_venue_id": "COMPOUNDV3-ETHEREUM",
        "lend_protocol": "Aave V3",
        "lend_venue_id": "AAVEV3-ETHEREUM",
        "token": "DAI",
        "chain": "ETHEREUM",
        "notional_usd": 800_000,
        "spread_captured_bps": 50,
        "health_factor": 3.10,
        "opened_at": "2026-04-12T16:45:00Z",
        "status": "active",
    },
    {
        "id": "pos-la-005",
        "borrow_protocol": "Aave V3",
        "borrow_venue_id": "AAVEV3-ETHEREUM",
        "lend_protocol": "Morpho Blue",
        "lend_venue_id": "MORPHO-ETHEREUM",
        "token": "USDC",
        "chain": "ETHEREUM",
        "notional_usd": 3_200_000,
        "spread_captured_bps": 90,
        "health_factor": 1.18,
        "opened_at": "2026-04-06T08:20:00Z",
        "status": "liquidation_risk",
    },
]


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class SimulateRateImpactRequest(BaseModel):  # CORRECT-LOCAL: API request model
    protocol: str
    token: str
    amount_usd: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rates")
async def get_lending_rates(
    request: Request,
) -> dict[str, object]:
    """Cross-protocol APY comparison for lending arb opportunities."""
    # In mock mode, return seed data directly.
    # In live mode, this would query features-onchain-service or GCS.
    return paginated_response(_SEED_RATES, page=1, page_size=50)


@router.get("/positions")
async def get_lending_positions(
    request: Request,
) -> dict[str, object]:
    """Active lending arb positions with health factor monitoring."""
    return paginated_response(_SEED_POSITIONS, page=1, page_size=50)


@router.post("/simulate-rate-impact")
async def simulate_rate_impact(
    request: Request,
    body: SimulateRateImpactRequest,
) -> dict[str, object]:
    """Simulate rate impact for a proposed deposit/borrow.

    Uses a simplified utilization curve model: larger deposits compress
    supply APY and increase borrow APY proportionally.
    """
    # Find current rates for protocol + token
    current = next(
        (r for r in _SEED_RATES if r["protocol"] == body.protocol and r["token"] == body.token),
        None,
    )
    if not current:
        return single_response(
            {"error": f"No rates for {body.protocol}/{body.token}"},
        )

    supply_val = current["supply_apy_pct"]
    borrow_val = current["borrow_apy_pct"]
    tvl_val = current["tvl_usd"]
    current_supply = float(str(supply_val))
    current_borrow = float(str(borrow_val))
    tvl = float(str(tvl_val))

    # Impact scales with amount relative to TVL
    impact_factor = body.amount_usd / max(tvl, 1.0)

    projected_supply = round(current_supply * (1 - impact_factor * 0.5), 4)
    projected_borrow = round(current_borrow * (1 + impact_factor * 0.3), 4)

    result = {
        "protocol": body.protocol,
        "token": body.token,
        "amount_usd": body.amount_usd,
        "current_supply_apy_pct": current_supply,
        "projected_supply_apy_pct": projected_supply,
        "current_borrow_apy_pct": current_borrow,
        "projected_borrow_apy_pct": projected_borrow,
        "rate_delta_supply_bps": round((projected_supply - current_supply) * 100),
        "rate_delta_borrow_bps": round((projected_borrow - current_borrow) * 100),
    }
    return single_response(result)
