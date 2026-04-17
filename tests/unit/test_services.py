"""Tests for services: GcsDomainService (LiveDomainService alias), MockDomainService, factory."""

from __future__ import annotations

from unittest.mock import patch

# ---------------------------------------------------------------------------
# LiveDomainService (GcsDomainService alias)
# ---------------------------------------------------------------------------


class TestLiveDomainService:
    """GcsDomainService returns empty results for unknown/static collections."""

    def test_list_returns_empty(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        with patch("unified_trading_api.services.live_service.get_storage_client"):
            svc = LiveDomainService(project_id="test-project")
        result = svc.list("orders")
        assert result == []

    def test_get_returns_none(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        with patch("unified_trading_api.services.live_service.get_storage_client"):
            svc = LiveDomainService(project_id="test-project")
        result = svc.get("orders", "o1")
        assert result is None

    def test_create_returns_data(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        with patch("unified_trading_api.services.live_service.get_storage_client"):
            svc = LiveDomainService(project_id="test-project")
        data: dict[str, object] = {"side": "BUY"}
        result = svc.create("orders", data)
        assert result == data

    def test_update_returns_data(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        with patch("unified_trading_api.services.live_service.get_storage_client"):
            svc = LiveDomainService(project_id="test-project")
        data: dict[str, object] = {"status": "filled"}
        result = svc.update("orders", "o1", data)
        assert result == data

    def test_delete_returns_false(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        with patch("unified_trading_api.services.live_service.get_storage_client"):
            svc = LiveDomainService(project_id="test-project")
        result = svc.delete("orders", "o1")
        assert result is False

    def test_reset_is_noop(self) -> None:
        from unified_trading_api.services.live_service import LiveDomainService

        with patch("unified_trading_api.services.live_service.get_storage_client"):
            svc = LiveDomainService(project_id="test-project")
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
