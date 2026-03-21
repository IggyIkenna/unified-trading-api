"""Health and readiness endpoints (unauthenticated)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Health check."""
    mock_mode = getattr(request.app.state, "mock_mode", True)
    start_time = getattr(request.app.state, "start_time", time.time())
    return {
        "status": "healthy",
        "version": "0.1.0",
        "mock_mode": mock_mode,
        "uptime_seconds": round(time.time() - start_time, 1),
    }


@router.get("/readiness")
async def readiness() -> dict[str, str]:
    """Readiness probe."""
    return {"status": "ready"}
