"""Standard response models for error handling and pagination."""

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
