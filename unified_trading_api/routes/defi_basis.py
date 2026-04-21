"""DeFi Basis Trade domain — enhanced funding matrix, LST collateral, venue allocation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    single_response,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/funding-matrix")
async def get_funding_matrix(request: Request) -> dict[str, object]:
    """Coin x Venue funding rate matrix (annualised %, OI, 24h change)."""
    service = get_service(request)
    records = service.list("basis_funding_matrix")
    matrix = records[0] if records else {}
    return single_response(matrix)


@router.get("/lst-collateral")
async def get_lst_collateral(request: Request) -> dict[str, object]:
    """LST collateral utilisation per open basis position."""
    service = get_service(request)
    records = service.list("basis_lst_collateral")
    return single_response(records)


@router.get("/venue-allocation")
async def get_venue_allocation(request: Request) -> dict[str, object]:
    """Cross-venue capital allocation for basis positions."""
    service = get_service(request)
    records = service.list("basis_venue_allocation")
    return single_response(records)


@router.get("/directions")
async def get_basis_directions(request: Request) -> dict[str, object]:
    """Standard vs inverse basis direction per coin based on funding sign."""
    service = get_service(request)
    records = service.list("basis_directions")
    return single_response(records)
