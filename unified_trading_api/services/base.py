"""Base service interface for domain data access.

Every domain (execution, positions, analytics, etc.) is served through
a DomainService. Mock and live implementations share this interface.
Route handlers only depend on this interface — they never know whether
data comes from MockStateStore or a real backend service.
"""

from __future__ import annotations

from typing import Protocol


class DomainService(Protocol):
    """Protocol for domain data access.

    All domain services implement these CRUD methods. The route handler
    calls these without knowing mock vs real.
    """

    def list(
        self,
        collection: str,
        filters: dict[str, str | int | float | bool | None] | None = None,
    ) -> list[dict[str, object]]:
        """List records, optionally filtered."""
        ...

    def get(self, collection: str, record_id: str) -> dict[str, object] | None:
        """Get a single record by ID."""
        ...

    def create(self, collection: str, data: dict[str, object]) -> dict[str, object]:
        """Create a new record. Returns the created record with ID."""
        ...

    def update(self, collection: str, record_id: str, data: dict[str, object]) -> dict[str, object] | None:
        """Update a record. Returns updated record or None if not found."""
        ...

    def delete(self, collection: str, record_id: str) -> bool:
        """Delete a record. Returns True if deleted."""
        ...

    def reset(self) -> None:
        """Reset to seed state (mock only — no-op in live)."""
        ...
