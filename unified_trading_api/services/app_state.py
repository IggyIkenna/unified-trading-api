"""Typed accessors for FastAPI app.state attributes.

``request.app.state.*`` returns ``Any`` because Starlette's State is an
open-ended attribute bag. These helpers use ``cast`` with suppressed
reportAny so downstream code is fully typed.
"""

from __future__ import annotations

import time
from typing import cast

from fastapi import Request
from starlette.websockets import WebSocket

from unified_trading_api.services.base import DomainService


def get_mock_mode(request: Request) -> bool:
    """Whether the app is running in mock mode."""
    return cast(bool, getattr(request.app.state, "mock_mode", False))  # pyright: ignore[reportAny]


def get_mock_mode_ws(ws: WebSocket) -> bool:
    """Whether the app is running in mock mode (WebSocket variant)."""
    return cast(bool, getattr(ws.app.state, "mock_mode", True))  # pyright: ignore[reportAny]


def get_disable_auth(request: Request) -> bool:
    """Whether auth is disabled (set in lifespan from UnifiedCloudConfig)."""
    return cast(bool, getattr(request.app.state, "disable_auth", False))  # pyright: ignore[reportAny]


def get_start_time(request: Request) -> float:
    """App start timestamp (set in lifespan)."""
    return cast(float, getattr(request.app.state, "start_time", time.time()))  # pyright: ignore[reportAny]


def get_service_from_state(request: Request) -> DomainService:
    """Extract the DomainService from app state (set in lifespan)."""
    service: DomainService = request.app.state.service  # pyright: ignore[reportAny]
    return service


def get_mock_store_raw(request: Request) -> object:
    """Extract the MockStateStore from app state as object.

    Callers that need typed store methods should import MockStateStore
    and use ``isinstance()`` to narrow.
    """
    store: object = getattr(request.app.state, "mock_store", None)  # pyright: ignore[reportAny]
    return store


def get_mock_store_ws(ws: WebSocket) -> object | None:
    """Extract the MockStateStore from app state (WebSocket variant)."""
    return cast(object, getattr(ws.app.state, "mock_store", None))  # pyright: ignore[reportAny]
