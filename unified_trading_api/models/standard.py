"""Standard response models for error handling and pagination."""

# SCHEMA_PROVENANCE_EXEMPT: ErrorDetail / PaginationMeta / StandardErrorResponse are
# API response envelopes owned by this gateway. They describe the HTTP response shape,
# not a cross-service domain contract — promoting them to UAC would just add a hop.

from __future__ import annotations

import uuid
from collections.abc import Sequence

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):  # CORRECT-LOCAL: API response model
    code: str
    message: str
    details: dict[str, object] | None = None


class StandardErrorResponse(BaseModel):  # CORRECT-LOCAL: API response model
    error: ErrorDetail
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])


class PaginationMeta(BaseModel):  # CORRECT-LOCAL: API response model
    total: int
    page: int
    page_size: int
    has_next: bool


def paginate(
    records: Sequence[object], page: int = 1, page_size: int = 50
) -> tuple[Sequence[object], PaginationMeta]:
    """Slice a list and return (page_data, pagination_meta)."""
    total = len(records)
    offset = (page - 1) * page_size
    data = records[offset : offset + page_size]
    return data, PaginationMeta(
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )


def paginated_response(
    records: Sequence[object],
    page: int = 1,
    page_size: int = 50,
    mode: str = "live",
    as_of: str | None = None,
    **extra: object,
) -> dict[str, object]:
    """Standard paginated response envelope.

    Returns::

        {
            "data": [...],
            "pagination": {"page": 1, "page_size": 50, "total": N, "has_next": bool},
            "mode": "live",
            "as_of": null,
            ...extra
        }
    """
    data, pagination = paginate(records, page, page_size)
    result: dict[str, object] = {
        "data": data,
        "pagination": pagination.model_dump(),
        "mode": mode,
        "as_of": as_of,
    }
    result.update(extra)
    return result


def single_response(
    data: object,
    mode: str = "live",
    as_of: str | None = None,
    **extra: object,
) -> dict[str, object]:
    """Standard single-object response envelope.

    Returns::

        {
            "data": {object or list},
            "mode": "live",
            "as_of": null,
            ...extra
        }
    """
    result: dict[str, object] = {
        "data": data,
        "mode": mode,
        "as_of": as_of,
    }
    result.update(extra)
    return result
