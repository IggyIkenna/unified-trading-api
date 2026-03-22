"""Standard response models for error handling and pagination."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


class StandardErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    has_next: bool


def paginate(
    records: list[object], page: int = 1, page_size: int = 50
) -> tuple[list[object], PaginationMeta]:
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
