"""Mock implementation of DomainService backed by UTL MockStateStore.

Provides the SAME filtering, pagination, and validation logic that a
real implementation would — only the data source differs.

Org-scoping: when a persona's org_id is set, list() automatically
filters records by org_id. Admin/internal personas (org_id=None or
org_id="odum-internal") see all data.
"""

from __future__ import annotations

import logging

from unified_trading_library import MockStateStore

logger = logging.getLogger(__name__)

_INTERNAL_ORGS = frozenset({"odum-internal"})


class MockDomainService:
    """Domain service backed by UTL MockStateStore with JSONL persistence.

    Supports org-scoped queries: set ``persona_org_id`` to filter records
    by org_id automatically. Admin/internal orgs bypass the filter.
    """

    def __init__(self, store: MockStateStore) -> None:
        self._store: MockStateStore = store
        self.persona_org_id: str | None = None
        self.persona_role: str | None = None

    def _apply_org_scope(self, records: list[dict[str, object]]) -> list[dict[str, object]]:
        """Filter by org_id if persona is a client (not admin/internal)."""
        if self.persona_role in ("admin", "internal") or self.persona_org_id is None:
            return records
        if self.persona_org_id in _INTERNAL_ORGS:
            return records
        return [r for r in records if r.get("org_id") == self.persona_org_id]

    def list(
        self,
        collection: str,
        filters: dict[str, str | int | float | bool | None] | None = None,
    ) -> list[dict[str, object]]:
        """List records with optional key-value filtering + org scoping."""
        records = self._store.list(collection)
        records = self._apply_org_scope(records)
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
        """Get a single record by ID (respects org scope)."""
        record = self._store.get(collection, record_id)
        if record is None:
            return None
        if self.persona_role in ("admin", "internal") or self.persona_org_id is None:
            return record
        if self.persona_org_id in _INTERNAL_ORGS:
            return record
        if record.get("org_id") == self.persona_org_id:
            return record
        return None

    def create(self, collection: str, data: dict[str, object]) -> dict[str, object]:
        """Create a new record (auto-tags with persona's org_id)."""
        if self.persona_org_id and "org_id" not in data:
            data["org_id"] = self.persona_org_id
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
