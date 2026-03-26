"""Tests for configuration patterns in the unified-trading-api.

Verifies that the service uses UnifiedCloudConfig from
unified_trading_library.config_interface for all config access, and that app_state
helpers correctly expose config values from app.state.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def _make_stub_service() -> MagicMock:
    """Create a stub DomainService that returns empty lists."""
    svc = MagicMock()
    svc.list.return_value = []
    svc.get.return_value = None
    svc.create.return_value = {}
    svc.update.return_value = None
    svc.delete.return_value = False
    return svc


@pytest.fixture
def mock_client() -> TestClient:
    """Create a test client in mock mode with auth disabled."""
    from unified_trading_api.main import create_app

    app = create_app()
    app.state.mock_mode = True
    app.state.disable_auth = True
    app.state.start_time = 1000.0
    app.state.service = _make_stub_service()
    return TestClient(app)


class TestUnifiedCloudConfigUsage:
    """Verify UnifiedCloudConfig is the config source, not raw os.getenv."""

    def test_main_imports_unified_cloud_config(self) -> None:
        """main.py should import UnifiedCloudConfig from unified_trading_library.config_interface."""
        import inspect

        from unified_trading_api import main

        source = inspect.getsource(main)
        assert "from unified_trading_library import UnifiedCloudConfig" in source

    def test_auth_imports_unified_cloud_config(self) -> None:
        """auth.py should import UnifiedCloudConfig for credential access."""
        import inspect

        from unified_trading_api.middleware import auth

        source = inspect.getsource(auth)
        assert "from unified_trading_library import UnifiedCloudConfig" in source

    def test_health_imports_unified_cloud_config(self) -> None:
        """health.py should import UnifiedCloudConfig for cloud_provider."""
        import inspect

        from unified_trading_api.routes import health

        source = inspect.getsource(health)
        assert "from unified_trading_library import UnifiedCloudConfig" in source

    def test_auth_module_creates_config_instance(self) -> None:
        """auth.py should have a module-level _auth_cfg instance."""
        from unified_trading_library import UnifiedCloudConfig

        from unified_trading_api.middleware import auth

        assert hasattr(auth, "_auth_cfg")
        assert isinstance(auth._auth_cfg, UnifiedCloudConfig)


class TestAppStateHelpers:
    """Test the typed accessors in services/app_state.py."""

    def _make_request(self, **state_attrs: object) -> MagicMock:
        """Create a mock Request with given app.state attributes."""
        mock_request = MagicMock()
        for attr, value in state_attrs.items():
            setattr(mock_request.app.state, attr, value)
        return mock_request

    def test_get_mock_mode_true(self) -> None:
        """get_mock_mode returns True when app.state.mock_mode is True."""
        from unified_trading_api.services.app_state import get_mock_mode

        request = self._make_request(mock_mode=True)
        assert get_mock_mode(request) is True

    def test_get_mock_mode_false(self) -> None:
        """get_mock_mode returns False when app.state.mock_mode is False."""
        from unified_trading_api.services.app_state import get_mock_mode

        request = self._make_request(mock_mode=False)
        assert get_mock_mode(request) is False

    def test_get_disable_auth_true(self) -> None:
        """get_disable_auth returns True when app.state.disable_auth is True."""
        from unified_trading_api.services.app_state import get_disable_auth

        request = self._make_request(disable_auth=True)
        assert get_disable_auth(request) is True

    def test_get_disable_auth_false(self) -> None:
        """get_disable_auth returns False when app.state.disable_auth is False."""
        from unified_trading_api.services.app_state import get_disable_auth

        request = self._make_request(disable_auth=False)
        assert get_disable_auth(request) is False

    def test_get_start_time(self) -> None:
        """get_start_time returns the value from app.state.start_time."""
        from unified_trading_api.services.app_state import get_start_time

        request = self._make_request(start_time=12345.6)
        assert get_start_time(request) == 12345.6

    def test_get_service_from_state(self) -> None:
        """get_service_from_state returns the service from app.state."""
        from unified_trading_api.services.app_state import get_service_from_state

        mock_service = MagicMock()
        request = self._make_request(service=mock_service)
        assert get_service_from_state(request) is mock_service


class TestHealthEndpointConfig:
    """Verify health/readiness endpoints expose config values."""

    def test_health_includes_cloud_provider(self, mock_client: TestClient) -> None:
        """Health endpoint should include cloud_provider from UnifiedCloudConfig."""
        response = mock_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "cloud_provider" in data
        assert isinstance(data["cloud_provider"], str)

    def test_health_includes_mock_mode(self, mock_client: TestClient) -> None:
        """Health endpoint should include mock_mode from UnifiedCloudConfig."""
        response = mock_client.get("/health")
        data = response.json()
        assert "mock_mode" in data
        assert isinstance(data["mock_mode"], bool)

    def test_readiness_includes_app_env(self, mock_client: TestClient) -> None:
        """Readiness endpoint should include app_env from UnifiedCloudConfig."""
        response = mock_client.get("/readiness")
        assert response.status_code == 200
        data = response.json()
        assert "app_env" in data
        assert isinstance(data["app_env"], str)

    def test_readiness_includes_disable_auth(self, mock_client: TestClient) -> None:
        """Readiness endpoint should report disable_auth state."""
        response = mock_client.get("/readiness")
        data = response.json()
        assert "disable_auth" in data
        assert data["disable_auth"] is True  # We set it in fixture


class TestConfigRoute:
    """Test the /config endpoints return data from the service."""

    def test_system_config_returns_200(self, mock_client: TestClient) -> None:
        """GET /config/system should return 200 with config key."""
        response = mock_client.get("/config/system")
        assert response.status_code == 200
        data = response.json()
        assert "config" in data

    def test_venue_config_returns_200(self, mock_client: TestClient) -> None:
        """GET /config/venues should return 200 with venues key."""
        response = mock_client.get("/config/venues")
        assert response.status_code == 200
        data = response.json()
        assert "venues" in data

    def test_feature_flags_returns_200(self, mock_client: TestClient) -> None:
        """GET /config/feature-flags should return 200 with feature_flags key."""
        response = mock_client.get("/config/feature-flags")
        assert response.status_code == 200
        data = response.json()
        assert "feature_flags" in data


class TestEntitlementConfig:
    """Test entitlement context derives from config/auth state."""

    def test_mock_mode_returns_internal_context(self) -> None:
        """When auth disabled, entitlement context should be internal."""
        from unified_trading_api.middleware.entitlement import (
            OrgType,
            get_entitlement_context,
        )

        mock_request = MagicMock()
        mock_request.app.state.disable_auth = True

        ctx = get_entitlement_context(mock_request)
        assert ctx.org_type == OrgType.INTERNAL
        assert ctx.is_internal is True
        assert ctx.org_id == "mock-org"
        assert ctx.tier == "enterprise"

    def test_real_mode_uses_auth_claims(self) -> None:
        """When auth enabled, entitlement context comes from JWT claims."""
        from unified_trading_api.middleware.entitlement import (
            OrgType,
            get_entitlement_context,
        )

        mock_request = MagicMock()
        mock_request.app.state.disable_auth = False
        mock_request.state.auth_claims = {
            "org_id": "acme-corp",
            "org_type": "external",
            "tier": "pro",
            "max_instruments": 500,
        }

        ctx = get_entitlement_context(mock_request)
        assert ctx.org_type == OrgType.EXTERNAL
        assert ctx.is_internal is False
        assert ctx.org_id == "acme-corp"
        assert ctx.tier == "pro"
        assert ctx.max_instruments == 500
