"""Service factory — returns mock or live implementation based on app state.

Usage in routes:
    from unified_trading_api.services.factory import get_service

    @router.get("/orders")
    async def get_orders(
        request: Request,
        service: DomainService = Depends(get_service),
    ):
        records = service.list("orders", filters={"venue": venue})
        ...
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from unified_trading_api.services.base import DomainService


def get_service(request: Request) -> DomainService:
    """FastAPI dependency that returns the correct service implementation.

    In mock mode: returns MockDomainService backed by UTL MockStateStore.
    In real mode: returns LiveDomainService (stubs).

    The service is stored on app.state by the lifespan handler.
    """
    return request.app.state.service  # type: ignore[no-any-return]


def get_service_dep() -> Callable[[Request], DomainService]:
    """Return the get_service dependency for use with Depends()."""
    return get_service
