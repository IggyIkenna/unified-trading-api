"""Instruments domain — list, catalogue, registry, mock lifecycle.

Mock endpoints (POST/DELETE /mock/*) are only available when is_mock_mode().
They mutate the InstrumentGenerator's ad-hoc pool for scenario testing:
  - Create fake instruments with custom strikes, expiries, venues
  - Delete/delist instruments mid-session
  - Expire instruments (set available_to=now)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from unified_api_contracts.internal.testing.instrument_generator import InstrumentGenerator

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.app_state import get_mock_mode
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/list")
async def get_instruments(
    request: Request,
    venue: str = Query(None),
    asset_class: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get instruments list."""
    service = get_service(request)
    records = service.list("instruments", filters={"venue": venue, "asset_class": asset_class})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/catalogue")
async def get_catalogue(
    request: Request,
) -> dict[str, object]:
    """Get instrument catalogue with metadata."""
    service = get_service(request)
    return {"catalogue": service.list("instrument_catalogue")}


@router.get("/registry")
async def get_registry(
    request: Request,
) -> dict[str, object]:
    """Get instrument registry — canonical mapping across venues."""
    service = get_service(request)
    return {"registry": service.list("instrument_registry")}


# ---------------------------------------------------------------------------
# Mock instrument lifecycle (Layer 3) — only available in mock mode
# ---------------------------------------------------------------------------


def _require_mock_mode(request: Request) -> None:
    """Raise 403 if not in mock mode."""
    if not get_mock_mode(request):
        raise HTTPException(
            status_code=403, detail="Mock instrument endpoints only available in mock mode"
        )


def _get_generator(request: Request) -> InstrumentGenerator:
    """Get or create the shared InstrumentGenerator on app state."""
    gen = cast(
        InstrumentGenerator | None,
        getattr(request.app.state, "_instrument_generator", None),  # pyright: ignore[reportAny]
    )
    if gen is None:
        gen = InstrumentGenerator(seed=42)
        request.app.state._instrument_generator = gen  # pyright: ignore[reportAny]
    return gen


class MockInstrumentCreate(BaseModel):  # CORRECT-LOCAL: API request body
    """Request body for creating a mock instrument."""

    venue: str
    instrument_type: str
    symbol: str
    base_asset: str = ""
    quote_asset: str = "USD"
    asset_class: str = ""
    strike: float | None = None
    option_type: str | None = None
    expiry: str | None = None
    underlying: str | None = None
    tick_size: float | None = None
    contract_size: float | None = None
    pool_address: str | None = None


@router.post("/mock/create")
async def create_mock_instrument(
    request: Request,
    body: MockInstrumentCreate,
) -> dict[str, object]:
    """Create a test instrument at runtime (mock mode only).

    Adds the instrument to the InstrumentGenerator's ad-hoc pool.
    It will appear in subsequent generate_all() calls.
    """
    _require_mock_mode(request)
    gen = _get_generator(request)

    kwargs: dict[str, str | float | int | None] = {
        "venue": body.venue,
        "instrument_type": body.instrument_type,
        "symbol": body.symbol,
        "base_asset": body.base_asset,
        "quote_asset": body.quote_asset,
        "asset_class": body.asset_class,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if body.strike is not None:
        kwargs["strike"] = body.strike
    if body.option_type is not None:
        kwargs["option_type"] = body.option_type
    if body.expiry is not None:
        kwargs["expiry"] = body.expiry
    if body.underlying is not None:
        kwargs["underlying"] = body.underlying
    if body.tick_size is not None:
        kwargs["tick_size"] = body.tick_size
    if body.contract_size is not None:
        kwargs["contract_size"] = body.contract_size
    if body.pool_address is not None:
        kwargs["pool_address"] = body.pool_address

    inst = gen.create_instrument(**kwargs)
    return {"status": "created", "instrument_key": inst.instrument_key}


@router.delete("/mock/{key:path}")
async def delete_mock_instrument(
    request: Request,
    key: str,
) -> dict[str, object]:
    """Remove/delist a test instrument (mock mode only).

    Supports glob patterns: DELETE /instruments/mock/DERIBIT:OPTION:BTC-*
    """
    _require_mock_mode(request)
    gen = _get_generator(request)
    count = gen.delete_instrument(key)
    return {"status": "deleted", "pattern": key, "count": count}


@router.post("/mock/expire/{key:path}")
async def expire_mock_instrument(
    request: Request,
    key: str,
) -> dict[str, object]:
    """Expire a test instrument (set available_to=now, mock mode only).

    Supports glob patterns: POST /instruments/mock/expire/DERIBIT:OPTION:BTC-*
    """
    _require_mock_mode(request)
    gen = _get_generator(request)
    count = gen.expire_instrument(key)
    return {"status": "expired", "pattern": key, "count": count}
