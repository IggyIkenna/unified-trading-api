"""Positions domain — active positions, summary, balances.

The ``/reconciliation/*`` routes below proxy strategy-service/position's real
reconciliation API (``strategy_service/position/api/reconciliation_routes.py``)
for the UI's ``use-reports.ts`` live-reconciliation hooks
(``useReconciliationDeviations``/``Balances``/``PnL``/``Summary``/
``useResolveDeviation``/``useAutoReconHistory``) — mirrors the BLRS
break-resolution proxy pattern already shipped in ``routes/reporting.py``.
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from unified_api_contracts.internal import ReconciliationAction  # noqa: qg-deep-import

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

# strategy-service base URL — reuses the same env slot routes/health.py and
# strategy_performance.py's PBM adapter probe (LIVE_SERVICE_STRATEGY_URL is
# already the registered strategy-service upstream; no new port invented).
_STRATEGY_SERVICE_URL_ENV = "LIVE_SERVICE_STRATEGY_URL"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/active")
async def get_active_positions(
    request: Request,
    venue: str = Query(None),
    strategy_id: str = Query(None),
    client_id: str = Query(None, description="Filter by client ID"),
    category: str = Query(None, description="Filter by category (CEFI, DEFI, TRADFI, SPORTS)"),
    strategy_family: str = Query(None, description="Filter by strategy family"),
    account_id: str = Query(None, description="Filter by account ID"),
    chain: str = Query(None, description="Filter by chain (e.g. ETHEREUM, SOLANA)"),
    mode: str = Query("live", pattern="^(live|batch)$"),
    as_of: str = Query(None, description="T+1 reconciliation date for batch mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get currently active positions with live/batch mode."""
    service = get_service(request)
    collection = f"positions_{mode}"
    records = service.list(
        collection,
        filters={
            "venue": venue,
            "strategy_id": strategy_id,
            "client_id": client_id,
            "category": category,
            "strategy_family": strategy_family,
            "account_id": account_id,
            "chain": chain,
            "as_of": as_of,
        },
    )
    return paginated_response(records, page, page_size, mode=mode, as_of=as_of)


@router.get("/summary")
async def get_position_summary(
    request: Request,
    mode: str = Query("live", pattern="^(live|batch)$"),
) -> dict[str, object]:
    """Get aggregated position summary across venues."""
    service = get_service(request)
    return single_response(service.list("position_summary"), mode=mode)


@router.get("/balances")
async def get_balances(
    request: Request,
    venue: str = Query(None),
    client_id: str = Query(None, description="Filter by client ID"),
    account_id: str = Query(None, description="Filter by account ID"),
    chain: str = Query(None, description="Filter by chain (e.g. ETHEREUM, SOLANA)"),
    mode: str = Query("live", pattern="^(live|batch)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get account balances across venues."""
    service = get_service(request)
    records = service.list(
        "balances",
        filters={
            "venue": venue,
            "client_id": client_id,
            "account_id": account_id,
            "chain": chain,
        },
    )
    return paginated_response(records, page, page_size, mode=mode)


# ---------------------------------------------------------------------------
# Reconciliation proxy (strategy-service/position)
# ---------------------------------------------------------------------------


async def _strategy_recon_proxy(
    request: Request,
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
) -> httpx.Response | None:
    """Proxy a request to strategy-service/position's ``/reconciliation/*`` API.

    Returns None when in mock mode, no strategy-service URL is configured, or
    the round trip itself fails (network/connection error) — callers fall
    back to MockStateStore in all three cases. A completed HTTP round-trip
    (any status code, including a 4xx/5xx from strategy-service) always
    returns the Response so the caller can forward the real status code to
    the UI rather than masking it as mock-mode.
    """
    mock_mode: bool = getattr(request.app.state, "mock_mode", True)  # pyright: ignore[reportAny]
    base_url = os.environ.get(_STRATEGY_SERVICE_URL_ENV)  # config-bootstrap:
    if mock_mode or not base_url:
        return None
    try:
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=10.0) as client:
            return await client.request(method, f"/reconciliation{path}", params=params, json=json_body)
    except (httpx.HTTPError, OSError):
        logger.exception("Failed to proxy %s %s to strategy-service/position", method, path)
        return None


@router.get("/reconciliation/deviations")
async def get_reconciliation_deviations(
    request: Request,
    status: str = Query(None),
) -> object:
    """List active reconciliation deviations — proxies strategy-service's
    ``GET /reconciliation/deviations``.

    Mock mode: served from the ``recon_deviations`` MockStateStore collection
    (empty until seeded — never masking a genuine zero-deviation day).
    """
    params: dict[str, str] = {"status": status} if status else {}
    resp = await _strategy_recon_proxy(request, "GET", "/deviations", params=params)
    if resp is not None:
        return JSONResponse(resp.json(), status_code=resp.status_code)  # pyright: ignore[reportAny]
    service = get_service(request)
    return service.list("recon_deviations", filters={"status": status.upper() if status else None})


@router.get("/reconciliation/balances")
async def get_reconciliation_balances(
    request: Request,
    venue: str = Query(None),
) -> object:
    """List recent balance-reconciliation snapshots — proxies strategy-service's
    ``GET /reconciliation/balances``.
    """
    params: dict[str, str] = {"venue": venue} if venue else {}
    resp = await _strategy_recon_proxy(request, "GET", "/balances", params=params)
    if resp is not None:
        return JSONResponse(resp.json(), status_code=resp.status_code)  # pyright: ignore[reportAny]
    service = get_service(request)
    return service.list("recon_balances", filters={"venue": venue})


@router.get("/reconciliation/pnl")
async def get_reconciliation_pnl(
    request: Request,
    venue: str = Query(None),
) -> object:
    """List recent PnL-reconciliation snapshots — proxies strategy-service's
    ``GET /reconciliation/pnl``.
    """
    params: dict[str, str] = {"venue": venue} if venue else {}
    resp = await _strategy_recon_proxy(request, "GET", "/pnl", params=params)
    if resp is not None:
        return JSONResponse(resp.json(), status_code=resp.status_code)  # pyright: ignore[reportAny]
    service = get_service(request)
    return service.list("recon_pnl", filters={"venue": venue})


class ReconciliationSummary(BaseModel):  # CORRECT-LOCAL — mirrors strategy-service's local response shape
    """Aggregate reconciliation-deviation counts by status."""

    total_deviations: int
    transient: int
    confirmed: int
    auto_reconciled: int
    escalated: int
    resolved: int
    last_run: str | None


@router.get("/reconciliation/summary")
async def get_reconciliation_summary(request: Request) -> object:
    """Aggregate reconciliation-deviation statistics — proxies strategy-service's
    ``GET /reconciliation/summary``.

    Mock mode: computed live from the ``recon_deviations`` mock collection
    (empty until seeded) rather than a hardcoded zero-state — ``last_run``
    stays None since mock mode has no real reconciliation run to report.
    """
    resp = await _strategy_recon_proxy(request, "GET", "/summary")
    if resp is not None:
        return JSONResponse(resp.json(), status_code=resp.status_code)  # pyright: ignore[reportAny]
    service = get_service(request)
    deviations = service.list("recon_deviations")
    return ReconciliationSummary(
        total_deviations=len(deviations),
        transient=sum(1 for d in deviations if d.get("status") == "TRANSIENT"),
        confirmed=sum(1 for d in deviations if d.get("status") == "CONFIRMED"),
        auto_reconciled=sum(1 for d in deviations if d.get("status") == "AUTO_RECONCILED"),
        escalated=sum(1 for d in deviations if d.get("status") == "ESCALATED"),
        resolved=sum(1 for d in deviations if d.get("status") == "RESOLVED"),
        last_run=None,
    )


class DeviationResolveRequest(BaseModel):  # CORRECT-LOCAL — mirrors strategy-service's local ResolveRequest shape
    """Request to resolve a reconciliation deviation."""

    deviation_id: str
    action: ReconciliationAction
    note: str = Field(min_length=10)
    resolved_by: str


_DEVIATION_ACTION_MESSAGES: dict[ReconciliationAction, str] = {
    ReconciliationAction.ACCEPT: "Deviation accepted as expected divergence",
    ReconciliationAction.REJECT: "Deviation rejected — correction required",
    ReconciliationAction.INVESTIGATE: "Deviation flagged for investigation",
}


@router.post("/reconciliation/resolve")
async def resolve_reconciliation_deviation(
    request: Request,
    resolution: DeviationResolveRequest,
) -> object:
    """Resolve a reconciliation deviation — proxies strategy-service's
    ``POST /reconciliation/resolve``.

    Mock mode: acknowledges the resolution without a live deviation tracker
    to validate it against — same low-stakes-ack convention as BLRS's own
    ``/resolve`` proxy in ``reporting.py`` (nothing here needs deriving from
    a real deviation, unlike book-correction).
    """
    resp = await _strategy_recon_proxy(request, "POST", "/resolve", json_body=resolution.model_dump(mode="json"))
    if resp is not None:
        return JSONResponse(resp.json(), status_code=resp.status_code)  # pyright: ignore[reportAny]
    return single_response(
        {
            "deviation_id": resolution.deviation_id,
            "action": resolution.action.value,
            "status": "resolved" if resolution.action != ReconciliationAction.INVESTIGATE else "investigating",
            "message": _DEVIATION_ACTION_MESSAGES.get(resolution.action, "Deviation resolved"),
        }
    )


@router.get("/reconciliation/auto-recon/history")
async def get_auto_recon_history(request: Request) -> object:
    """List auto-reconciled deviations — proxies strategy-service's
    ``GET /reconciliation/auto-recon/history``.

    Mock mode: served from the ``recon_auto_history`` MockStateStore
    collection (empty until seeded).
    """
    resp = await _strategy_recon_proxy(request, "GET", "/auto-recon/history")
    if resp is not None:
        return JSONResponse(resp.json(), status_code=resp.status_code)  # pyright: ignore[reportAny]
    service = get_service(request)
    return service.list("recon_auto_history")
