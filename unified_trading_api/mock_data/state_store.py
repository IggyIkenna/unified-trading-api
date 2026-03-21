"""MockStateStore — in-memory state store for mock mode.

Provides CRUD operations over seeded data. In real mode, routes call
backend services instead. The store is populated at startup by
seed_mock_data.py or domain-specific seed functions.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MockStateStore:
    """Thread-safe in-memory data store for mock mode."""

    def __init__(self) -> None:
        self._data: dict[str, list[dict[str, object]]] = defaultdict(list)

    def seed(self, domain: str, records: list[dict[str, object]]) -> None:
        """Seed a domain with initial records."""
        self._data[domain] = list(records)
        logger.info("Seeded %s with %d records", domain, len(records))

    def list(self, domain: str) -> list[dict[str, object]]:
        """List all records for a domain."""
        return list(self._data[domain])

    def get(self, domain: str, key: str, value: object) -> dict[str, object] | None:
        """Get a single record by key-value match."""
        for record in self._data[domain]:
            if record.get(key) == value:
                return dict(record)
        return None

    def add(self, domain: str, record: dict[str, object]) -> None:
        """Add a record to a domain."""
        self._data[domain].append(record)

    def update(self, domain: str, key: str, value: object, updates: dict[str, object]) -> bool:
        """Update a record in-place. Returns True if found."""
        for record in self._data[domain]:
            if record.get(key) == value:
                record.update(updates)
                return True
        return False

    def delete(self, domain: str, key: str, value: object) -> bool:
        """Delete a record. Returns True if found."""
        before = len(self._data[domain])
        self._data[domain] = [r for r in self._data[domain] if r.get(key) != value]
        return len(self._data[domain]) < before

    def clear(self, domain: str | None = None) -> None:
        """Clear one or all domains."""
        if domain:
            self._data[domain] = []
        else:
            self._data.clear()


# Singleton instance used by all routes in mock mode
mock_store = MockStateStore()
