"""Admin endpoints — reset demo state, health probes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from unified_trading_library import MockStateStore

from unified_trading_api.mock_data.seed import (  # noqa: qg-deep-import — self-package
    seed_all_domains,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.services.app_state import (  # noqa: qg-deep-import — self-package
    get_mock_mode,
    get_mock_store_raw,
    get_service_from_state,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reset")
async def reset_demo(request: Request) -> dict[str, str]:
    """Reset mock state to seed data. Clears all mutations.

    Only available in mock mode. In real mode, returns 403.
    The UI's "Reset Demo" button calls this endpoint.
    """
    if not get_mock_mode(request):
        return {"status": "forbidden", "message": "Reset only available in mock mode"}

    service = get_service_from_state(request)
    service.reset()

    # Re-seed from scratch
    raw_store = get_mock_store_raw(request)
    if isinstance(raw_store, MockStateStore):
        seed_all_domains(raw_store)

    logger.info("POST /admin/reset — mock state reset to seed")
    return {"status": "ok", "message": "Demo state reset to seed data"}
