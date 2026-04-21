"""Positions domain — active positions, summary, balances."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

router = APIRouter(dependencies=[Depends(verify_api_key)])


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
