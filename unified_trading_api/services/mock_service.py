"""Mock implementation of DomainService backed by UTL MockStateStore.

Provides the SAME filtering, pagination, and validation logic that a
real implementation would — only the data source differs.
"""

from __future__ import annotations

import logging

from unified_trading_library.core.mock_state_store import MockStateStore

logger = logging.getLogger(__name__)


class MockDomainService:
    """Domain service backed by UTL MockStateStore with JSONL persistence."""

    def __init__(self, store: MockStateStore) -> None:
        self._store = store

    def list(
        self,
        collection: str,
        filters: dict[str, str | int | float | bool | None] | None = None,
    ) -> list[dict[str, object]]:
        """List records with optional key-value filtering.

        Applies the SAME filtering logic that a real DB query would:
        exact match on each filter key.
        """
        records = self._store.list(collection)
        if not filters:
            return records
        result: list[dict[str, object]] = []
        for record in records:
            match = True
            for key, value in filters.items():
                if value is None:
                    continue
                if record.get(key) != value:
                    match = False
                    break
            if match:
                result.append(record)
        return result

    def get(self, collection: str, record_id: str) -> dict[str, object] | None:
        """Get a single record by ID."""
        return self._store.get(collection, record_id)

    def create(self, collection: str, data: dict[str, object]) -> dict[str, object]:
        """Create a new record."""
        return self._store.create(collection, data)

    def update(
        self, collection: str, record_id: str, data: dict[str, object]
    ) -> dict[str, object] | None:
        """Update a record."""
        return self._store.update(collection, record_id, data)

    def delete(self, collection: str, record_id: str) -> bool:
        """Delete a record."""
        return self._store.delete(collection, record_id)

    def reset(self) -> None:
        """Reset to seed state — clears mutations, keeps seed data."""
        self._store.reset()
        logger.info("MockDomainService: reset to seed state")
