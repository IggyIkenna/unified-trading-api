"""Admin endpoints — reset demo state, health probes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reset")
async def reset_demo(request: Request) -> dict[str, str]:
    """Reset mock state to seed data. Clears all mutations.

    Only available in mock mode. In real mode, returns 403.
    The UI's "Reset Demo" button calls this endpoint.
    """
    if not getattr(request.app.state, "mock_mode", False):
        return {"status": "forbidden", "message": "Reset only available in mock mode"}

    service = request.app.state.service
    service.reset()

    # Re-seed from scratch
    store = request.app.state.mock_store
    from unified_trading_api.mock_data.seed import seed_all_domains

    seed_all_domains(store)

    logger.info("POST /admin/reset — mock state reset to seed")
    return {"status": "ok", "message": "Demo state reset to seed data"}
