"""Tests for services: LiveDomainService, MockDomainService, state_store, factory."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# LiveDomainService
# ---------------------------------------------------------------------------


class TestLiveDomainService:
    """All methods except reset raise NotImplementedError."""

    def test_list_raises(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        svc = LiveDomainService()
        with pytest.raises(NotImplementedError, match="Live mode not wired"):
            svc.list("orders")

    def test_get_raises(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        svc = LiveDomainService()
        with pytest.raises(NotImplementedError, match="Live mode not wired"):
            svc.get("orders", "o1")

    def test_create_raises(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        svc = LiveDomainService()
        with pytest.raises(NotImplementedError, match="Live mode not wired"):
            svc.create("orders", {"side": "BUY"})

    def test_update_raises(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        svc = LiveDomainService()
        with pytest.raises(NotImplementedError, match="Live mode not wired"):
            svc.update("orders", "o1", {"status": "filled"})

    def test_delete_raises(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        svc = LiveDomainService()
        with pytest.raises(NotImplementedError, match="Live mode not wired"):
            svc.delete("orders", "o1")

    def test_reset_is_noop(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        svc = LiveDomainService()
        svc.reset()  # Should not raise


# ---------------------------------------------------------------------------
# DomainService Protocol
# ---------------------------------------------------------------------------


class TestDomainServiceProtocol:
    """Verify Protocol is well-formed and InMemoryService satisfies it."""

    def test_protocol_has_expected_methods(self) -> None:
        from unified_trading_api.services.base import DomainService

        assert hasattr(DomainService, "list")
        assert hasattr(DomainService, "get")
        assert hasattr(DomainService, "create")
        assert hasattr(DomainService, "update")
        assert hasattr(DomainService, "delete")
        assert hasattr(DomainService, "reset")


# ---------------------------------------------------------------------------
# MockStateStore (unified_trading_api/mock_data/state_store.py)
# ---------------------------------------------------------------------------


class TestMockStateStore:
    """Test the local MockStateStore (unified_trading_api.mock_data.state_store)."""

    def test_seed_and_list(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1"}, {"id": "o2"}])
        assert len(store.list("orders")) == 2

    def test_list_empty_domain(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        assert store.list("nonexistent") == []

    def test_get_found(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1", "status": "filled"}])
        result = store.get("orders", "id", "o1")
        assert result is not None
        assert result["status"] == "filled"

    def test_get_not_found(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1"}])
        assert store.get("orders", "id", "o99") is None

    def test_add(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.add("orders", {"id": "o1"})
        assert len(store.list("orders")) == 1

    def test_update_found(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1", "status": "open"}])
        assert store.update("orders", "id", "o1", {"status": "filled"}) is True
        record = store.get("orders", "id", "o1")
        assert record is not None
        assert record["status"] == "filled"

    def test_update_not_found(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        assert store.update("orders", "id", "o99", {"status": "filled"}) is False

    def test_delete_found(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1"}, {"id": "o2"}])
        assert store.delete("orders", "id", "o1") is True
        assert len(store.list("orders")) == 1

    def test_delete_not_found(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1"}])
        assert store.delete("orders", "id", "o99") is False

    def test_clear_domain(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1"}])
        store.seed("fills", [{"id": "f1"}])
        store.clear("orders")
        assert len(store.list("orders")) == 0
        assert len(store.list("fills")) == 1

    def test_clear_all(self) -> None:
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        store.seed("orders", [{"id": "o1"}])
        store.seed("fills", [{"id": "f1"}])
        store.clear()
        assert len(store.list("orders")) == 0
        assert len(store.list("fills")) == 0


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------


class TestServiceFactory:
    """Test get_service factory function."""

    def test_get_service_returns_service(self) -> None:
        from fastapi.testclient import TestClient

        from tests.unit.conftest import InMemoryService
        from unified_trading_api.main import create_app

        app = create_app()
        svc = InMemoryService()
        svc.seed("alert_summary", [{"total": 5}])
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0
        app.state.service = svc
        client = TestClient(app)

        # Just verify a route that uses get_service works
        resp = client.get("/alerts/summary")
        assert resp.status_code == 200

    def test_get_service_with_persona_header(self) -> None:
        from fastapi.testclient import TestClient

        from tests.unit.conftest import InMemoryService
        from unified_trading_api.main import create_app

        app = create_app()
        svc = InMemoryService()
        svc.seed("alert_summary", [{"total": 5}])
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0
        app.state.service = svc
        client = TestClient(app)

        resp = client.get("/alerts/summary", headers={"x-demo-persona": "admin"})
        assert resp.status_code == 200

    def test_get_service_with_unknown_persona(self) -> None:
        from fastapi.testclient import TestClient

        from tests.unit.conftest import InMemoryService
        from unified_trading_api.main import create_app

        app = create_app()
        svc = InMemoryService()
        svc.seed("alert_summary", [{"total": 5}])
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0
        app.state.service = svc
        client = TestClient(app)

        resp = client.get("/alerts/summary", headers={"x-demo-persona": "nonexistent"})
        assert resp.status_code == 200
