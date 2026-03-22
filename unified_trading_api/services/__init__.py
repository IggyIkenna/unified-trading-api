"""Service layer — abstracts mock/real data source from route handlers.

Routes call service methods (list, get, create, update, delete). The factory
returns a mock or live implementation based on app.state.mock_mode. Routes
never check mock_mode themselves.

Usage in routes:
    from unified_trading_api.services.factory import get_service

    @router.get("/orders")
    async def get_orders(request: Request, service = Depends(get_service("orders"))):
        records = service.list(venue=venue, status=status)
        ...
"""

from unified_trading_api.services.base import DomainService

__all__ = ["DomainService"]
