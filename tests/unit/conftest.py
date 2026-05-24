"""Shared fixtures for unit tests.

Provides a FastAPI TestClient with an in-memory DomainService stub
that requires no network, no file I/O, and no cloud credentials.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class InMemoryService:
    """Minimal DomainService implementation for unit tests.

    Stores records in memory with auto-generated IDs.
    Satisfies the DomainService protocol without any external deps.
    """

    def __init__(self) -> None:
        self._data: dict[str, list[dict[str, object]]] = {}
        self._counter: int = 0
        self.persona_org_id: str | None = None
        self.persona_role: str | None = None

    def seed(self, domain: str, records: list[dict[str, object]]) -> None:
        self._data[domain] = list(records)

    def list(
        self,
        collection: str,
        filters: dict[str, str | int | float | bool | None] | None = None,
    ) -> list[dict[str, object]]:
        records = list(self._data.get(collection, []))
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

    def get(
        self,
        collection: str,
        record_id: str | None = None,
        filters: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        if filters:
            records = self.list(collection, filters)
            return records[0] if records else None
        for record in self._data.get(collection, []):
            if record.get("id") == record_id:
                return dict(record)
        return None

    def create(self, collection: str, data: dict[str, object]) -> dict[str, object]:
        self._counter += 1
        record = {**data, "id": data.get("id", f"gen-{self._counter}")}
        self._data.setdefault(collection, []).append(record)
        return record

    def update(self, collection: str, record_id: str, data: dict[str, object]) -> dict[str, object] | None:
        for record in self._data.get(collection, []):
            if record.get("id") == record_id:
                record.update(data)
                return dict(record)
        return None

    def delete(self, collection: str, record_id: str) -> bool:
        records = self._data.get(collection, [])
        before = len(records)
        self._data[collection] = [r for r in records if r.get("id") != record_id]
        return len(self._data[collection]) < before

    def reset(self) -> None:
        self._data.clear()


@pytest.fixture
def mock_service() -> InMemoryService:
    """Create a fresh in-memory service."""
    return InMemoryService()


@pytest.fixture
def app_client(mock_service: InMemoryService) -> TestClient:
    """Create a TestClient with mock mode, auth disabled, and in-memory service."""
    from unified_trading_api.main import create_app

    app = create_app()
    app.state.mock_mode = True
    app.state.disable_auth = True
    app.state.start_time = 0.0
    app.state.service = mock_service
    app.state.mock_store = None  # admin/reset checks isinstance; None skips re-seed
    return TestClient(app)
