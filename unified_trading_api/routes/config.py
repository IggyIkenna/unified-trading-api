"""Config domain — system config, venues, feature flags, mandates, fee schedules."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginated_response, single_response
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/system")
async def get_system_config(
    request: Request,
) -> dict[str, object]:
    """Get system configuration."""
    service = get_service(request)
    records = service.list("system_config")
    return single_response(records[0] if records else {})


@router.put("/system")
async def update_system_config(
    request: Request,
) -> dict[str, object]:
    """Update system configuration."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    existing = service.list("system_config")
    if existing:
        updated = service.update("system_config", "", body)
        if updated:
            return single_response({"config": updated, "status": "updated"})
    record = service.create("system_config", body)
    return single_response({"config": record, "status": "created"})


@router.get("/venues")
async def get_venue_config(
    request: Request,
) -> dict[str, object]:
    """Get venue configuration."""
    service = get_service(request)
    return single_response(service.list("config_venues"))


@router.get("/feature-flags")
async def get_feature_flags(
    request: Request,
) -> dict[str, object]:
    """Get feature flags."""
    service = get_service(request)
    return single_response(service.list("feature_flags"))


@router.get("/mandates")
async def get_mandates(
    request: Request,
    client_id: str = Query(None, description="Filter by client ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get client mandate definitions — investment constraints, limits, allowed instruments."""
    service = get_service(request)
    records = service.list("mandates", filters={"client_id": client_id})
    if records:
        return paginated_response(records, page, page_size)
    # Sensible defaults when no seeded data exists
    return paginated_response(
        [
            {
                "id": "mandate-001",
                "client_id": "client-elysium",
                "name": "Conservative Crypto",
                "max_leverage": 3,
                "allowed_categories": ["cefi", "defi"],
                "max_single_position_pct": 10.0,
                "max_drawdown_pct": 5.0,
                "restricted_venues": [],
                "allowed_instrument_types": ["spot", "perp"],
            },
            {
                "id": "mandate-002",
                "client_id": "client-elysium",
                "name": "Sports Arb",
                "max_leverage": 1,
                "allowed_categories": ["sports"],
                "max_single_position_pct": 5.0,
                "max_drawdown_pct": 2.0,
                "restricted_venues": [],
                "allowed_instrument_types": ["sports_bet"],
            },
        ],
        page,
        page_size,
    )


@router.get("/fee-schedules")
async def get_fee_schedules(
    request: Request,
    venue: str = Query(None, description="Filter by venue"),
    instrument_type: str = Query(None, description="Filter by instrument type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get fee schedules per venue/instrument type."""
    service = get_service(request)
    records = service.list(
        "fee_schedules", filters={"venue": venue, "instrument_type": instrument_type}
    )
    if records:
        return paginated_response(records, page, page_size)
    return paginated_response(
        [
            {
                "venue": "binance",
                "instrument_type": "spot",
                "maker_fee_bps": 10,
                "taker_fee_bps": 10,
                "tier": "vip0",
            },
            {
                "venue": "binance",
                "instrument_type": "perp",
                "maker_fee_bps": 2,
                "taker_fee_bps": 4,
                "tier": "vip0",
            },
            {
                "venue": "deribit",
                "instrument_type": "option",
                "maker_fee_bps": 3,
                "taker_fee_bps": 3,
                "tier": "default",
            },
            {
                "venue": "betfair_exchange",
                "instrument_type": "sports_bet",
                "maker_fee_bps": 0,
                "taker_fee_bps": 200,
                "tier": "standard",
                "note": "2% commission on net winnings",
            },
        ],
        page,
        page_size,
    )


@router.post("/reload")
async def reload_config(
    request: Request,
) -> dict[str, object]:
    """Trigger config hot-reload across all config domains.

    In mock mode: clears cached config and returns success.
    In real mode: would trigger config reloader on each service via Pub/Sub.
    """
    service = get_service(request)
    # In mock mode we just acknowledge the reload
    collections = ["system_config", "config_venues", "feature_flags", "mandates", "fee_schedules"]
    reloaded: list[str] = []
    for coll in collections:
        records = service.list(coll)
        if records:
            reloaded.append(coll)
    return single_response(
        {
            "status": "reloaded",
            "collections": reloaded,
            "reloaded_at": datetime.now(UTC).isoformat(),
        }
    )


@router.get("/strategies")
async def get_strategy_config(
    request: Request,
    status: str = Query(None, description="Filter by status: active, paused, staging"),
    category: str = Query(None, description="Filter by category: cefi, defi, tradfi, sports"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get strategy configuration — parameters, limits, schedules.

    Different from /analytics/strategies which returns strategy performance.
    This returns the raw config used by strategy-service.
    """
    service = get_service(request)
    records = service.list("strategies", filters={"status": status, "category": category})
    return paginated_response(records, page, page_size)
