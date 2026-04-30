"""Instruments domain — list, catalogue, registry, mock lifecycle.

Mock endpoints (POST/DELETE /mock/*) are only available when is_mock_mode().
They mutate the InstrumentGenerator's ad-hoc pool for scenario testing:
  - Create fake instruments with custom strikes, expiries, venues
  - Delete/delist instruments mid-session
  - Expire instruments (set available_to=now)

"""

# SCHEMA_PROVENANCE_EXEMPT: MockInstrumentCreate is a mock-mode POST body used
# only by the test-scenario seeding endpoints; the canonical Instrument
# contract lives in UAC.

from __future__ import annotations

from datetime import UTC, datetime
from datetime import date as _Date
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from unified_api_contracts.internal.testing.instrument_generator import (  # noqa: qg-deep-import — UAC internal facade
    InstrumentGenerator,  # noqa: qg-deep-import — UAC internal facade
)

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.app_state import (  # noqa: qg-deep-import — self-package
    get_mock_mode,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package
from unified_trading_api.services.instruments_reader import (  # noqa: qg-deep-import — self-package
    InstrumentsReader,  # noqa: qg-deep-import — self-package
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _get_instruments_reader(request: Request) -> InstrumentsReader | None:
    """Lazily create + cache the InstrumentsReader on app.state."""
    existing = cast(
        InstrumentsReader | None,
        getattr(request.app.state, "_instruments_reader", None),  # pyright: ignore[reportAny]
    )
    if existing is not None:
        return existing
    project_id = cast(
        str | None,
        getattr(request.app.state.service, "_project_id", None),  # pyright: ignore[reportAny]
    )
    if not project_id:
        return None
    reader = InstrumentsReader(project_id=project_id)
    request.app.state._instruments_reader = reader  # pyright: ignore[reportAny]
    return reader


@router.get("/list")
async def get_instruments(
    request: Request,
    venue: str | None = Query(None),
    asset_group: str | None = Query(None),
    as_of: _Date | None = Query(None, description="UTC date for instrument availability snapshot"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get instruments list.

    Real mode:
      - With ``venue`` + ``asset_group``: reads one (date, venue) shard.
      - With only ``asset_group``: fans out across all venues that
        instruments-service published for the date (manifest-driven), in
        parallel.
      - With no filters: returns mock fixture list (the asset-group-less
        case is rarely useful for real GCS reads — would touch all 5
        buckets).

    Mock mode: returns the mock fixture list.
    """
    if get_mock_mode(request) or not asset_group:
        service = get_service(request)
        records = service.list(
            "instruments",
            filters={"venue": venue, "asset_group": asset_group},
        )
        return paginated_response(records, page, page_size)

    reader = _get_instruments_reader(request)
    if reader is None:
        return paginated_response([], page, page_size)

    if venue:
        records = reader.get_instruments(asset_group=asset_group, venue=venue, as_of=as_of)
    else:
        records = reader.get_instruments_multi_venue(asset_group=asset_group, as_of=as_of)
    # Dedupe by instrument_key — see /live-universe for context (upstream
    # collapses fiat-quote variants to the same canonical key).
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for r in records:
        k = r.get("instrument_key")
        if not isinstance(k, str) or not k or k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    return paginated_response(deduped, page, page_size)


@router.get("/live-universe")
async def get_live_universe(
    request: Request,
    asset_group: str = Query(..., description="cefi | tradfi | defi (one per call)"),
) -> dict[str, object]:
    """Return the full live-tradeable universe for one asset_group.

    One shipping payload per asset_group — UI fetches lazily (a TradFi-only
    user never pays for CEFI's 6K rows). Cached 1h via the same
    InstrumentsReader cache that backs ``/list``.

    Live = ``available_to_datetime`` is null OR strictly in the future. Filters
    out expired options/futures so the watchlist sees today's tradeable set
    only. Batch mode (with explicit ``as_of``) goes through ``/list`` instead
    — different access pattern, server-side filtering of the historical
    universe.

    Date selection: latest date in the manifest for this asset_group.
    Falls back to yesterday (UTC) if the manifest can't help.
    """
    if get_mock_mode(request):
        # Mock seed has the full instrument list already; just return it.
        service = get_service(request)
        records = service.list("instruments", filters={"asset_group": asset_group})
        return single_response(records, asset_group=asset_group)

    reader = _get_instruments_reader(request)
    if reader is None:
        return single_response([], asset_group=asset_group)

    target_date = reader.latest_date_with_data(asset_group)
    if target_date is None:
        target_date = (datetime.now(UTC).date())
    records = reader.get_instruments_multi_venue(
        asset_group=asset_group,
        as_of=target_date,
    )
    # Live filter: drop instruments whose available_to_datetime is in the past.
    # Dedupe by instrument_key — instruments-service occasionally writes
    # multiple rows per canonical key when distinct fiat-quote pairs (BTC-TRY,
    # BTC-AUD, …) collapse to the same canonical USD-quoted key in UAC's
    # build_instrument_id. That's an upstream bug; we keep the first row per
    # key here so downstream React keys stay unique. Tracked separately as
    # an instruments-service / UAC fix.
    now_iso = datetime.now(UTC).isoformat()
    live_records: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    for r in records:
        ato = r.get("available_to_datetime")
        if ato is not None and not (isinstance(ato, str) and ato > now_iso):
            continue
        key = r.get("instrument_key")
        if not isinstance(key, str) or not key:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        live_records.append(r)
    return single_response(
        live_records,
        asset_group=asset_group,
        as_of=target_date.isoformat(),
        total=len(live_records),
    )


@router.get("/catalogue")
async def get_catalogue(
    request: Request,
) -> dict[str, object]:
    """Get instrument catalogue with metadata."""
    service = get_service(request)
    return single_response(service.list("instrument_catalogue"))


@router.get("/registry")
async def get_registry(
    request: Request,
    venue: str = Query(None, description="Filter by venue (e.g. binance, deribit)"),
    asset_group: str = Query(None, description="Filter by asset group: cefi, defi, tradfi"),
    instrument_type: str = Query(
        None, description="Filter by type: spot, future, option, perp, lp_pool"
    ),
    status: str = Query(None, description="Filter by status: active, delisted, expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get instrument registry — canonical mapping across venues.

    Supports filtering by venue, asset_group, instrument_type, and status.
    Response includes trading_hours, tick_size, lot_size, fee_structure,
    and available_since where available.
    """
    service = get_service(request)
    records = service.list(
        "instrument_registry",
        filters={
            "venue": venue,
            "asset_group": asset_group,
            "instrument_type": instrument_type,
            "status": status,
        },
    )
    return paginated_response(records, page, page_size)


@router.get("/curated")
async def get_curated_instruments(
    asset_group: str | None = Query(None, description="Filter by asset group: cefi, defi, tradfi"),
) -> dict[str, object]:
    """Return curated instruments for the trading terminal watchlist.

    These are the symbols with confirmed GCS market data coverage.
    """
    from unified_trading_api.config.curated_symbols import CURATED_SYMBOLS  # noqa: qg-deep-import — self-package

    if asset_group:
        data: dict[str, object] = {asset_group: CURATED_SYMBOLS.get(asset_group.lower(), [])}
    else:
        data = dict(CURATED_SYMBOLS)
    return single_response(data)


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
    asset_group: str = ""
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
        "asset_group": body.asset_group,
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
    return single_response({"instrument_key": inst.instrument_key, "status": "created"})


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
    return single_response({"pattern": key, "count": count, "status": "deleted"})


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
    return single_response({"pattern": key, "count": count, "status": "expired"})
