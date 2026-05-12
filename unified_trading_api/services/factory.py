"""Service factory — returns mock or live implementation based on app state.

In mock mode, extracts the persona from X-Demo-Persona header and sets
org_id scoping on the MockDomainService so clients only see their data.
"""

from __future__ import annotations

from fastapi import Request

from unified_trading_api.mock_data.personas import PERSONAS  # noqa: qg-deep-import — self-package
from unified_trading_api.services.app_state import (  # noqa: qg-deep-import — self-package
    get_service_from_state,
)
from unified_trading_api.services.base import DomainService  # noqa: qg-deep-import — self-package


def get_service(request: Request) -> DomainService:
    """FastAPI dependency that returns the correct service implementation.

    In mock mode: returns MockDomainService backed by UTL MockStateStore.
    Sets persona_org_id from X-Demo-Persona header for org-scoped queries.
    In real mode: returns LiveDomainService (stubs).
    """
    service = get_service_from_state(request)

    # Apply org scoping from persona header (mock mode only)
    persona_id = request.headers.get("x-demo-persona")
    if persona_id and hasattr(service, "persona_org_id"):
        persona = next((p for p in PERSONAS if p["id"] == persona_id), None)
        if persona:
            setattr(service, "persona_org_id", str(persona["org_id"]))
            setattr(service, "persona_role", str(persona["role"]))
        else:
            setattr(service, "persona_org_id", None)
            setattr(service, "persona_role", None)
    elif hasattr(service, "persona_org_id"):
        setattr(service, "persona_org_id", None)
        setattr(service, "persona_role", None)

    return service
