"""Tests for event logging patterns in the unified-trading-api.

Verifies that auth middleware uses unified_events_interface.log_event
for structured event emission (AUTH_FAILURE, AUTH_MISCONFIGURED) and
that standard Python logging is used throughout the codebase.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
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
def mock_app_client() -> TestClient:
    """Create a test client with auth disabled (mock mode)."""
    from unified_trading_api.main import create_app

    app = create_app()
    app.state.mock_mode = True
    app.state.disable_auth = True
    app.state.start_time = 0.0
    app.state.service = _make_stub_service()
    return TestClient(app)


@pytest.fixture
def auth_enabled_client() -> TestClient:
    """Create a test client with auth enabled."""
    from unified_trading_api.main import create_app

    app = create_app()
    app.state.mock_mode = False
    app.state.disable_auth = False
    app.state.start_time = 0.0
    return TestClient(app)


class TestAuthEventLogging:
    """Test that auth middleware emits structured events via log_event."""

    def test_missing_api_key_emits_auth_failure(self, auth_enabled_client: TestClient) -> None:
        """Requests without X-API-Key should emit AUTH_FAILURE event."""
        with patch("unified_trading_api.middleware.auth.log_event") as mock_log_event:
            response = auth_enabled_client.get("/config/system")
            assert response.status_code == 401

            # log_event should have been called with AUTH_FAILURE
            calls = [c for c in mock_log_event.call_args_list if c.args[0] == "AUTH_FAILURE"]
            assert len(calls) >= 1
            call_kwargs = calls[0].kwargs if calls[0].kwargs else {}
            call_details = call_kwargs.get("details") or (
                calls[0].args[2] if len(calls[0].args) > 2 else {}
            )
            # The details dict should include reason
            assert call_details.get("reason") == "missing_key"

    def test_invalid_api_key_emits_auth_failure(self, auth_enabled_client: TestClient) -> None:
        """Requests with wrong X-API-Key should emit AUTH_FAILURE event."""
        with patch("unified_trading_api.middleware.auth.log_event") as mock_log_event:
            with patch("unified_trading_api.middleware.auth._auth_cfg") as mock_cfg:
                mock_cfg.api_key = "correct-key"
                mock_cfg.disable_auth = False

                response = auth_enabled_client.get(
                    "/config/system",
                    headers={"X-API-Key": "wrong-key"},
                )
                assert response.status_code == 401

                calls = [c for c in mock_log_event.call_args_list if c.args[0] == "AUTH_FAILURE"]
                assert len(calls) >= 1

    def test_auth_disabled_skips_key_validation(self, mock_app_client: TestClient) -> None:
        """When auth is disabled, verify_api_key returns 'dev-mode' without events."""
        with patch("unified_trading_api.middleware.auth.log_event") as mock_log_event:
            response = mock_app_client.get("/config/system")
            # Should succeed without auth
            assert response.status_code == 200

            # AUTH_FAILURE should NOT have been emitted
            failure_calls = [
                c for c in mock_log_event.call_args_list if c.args and c.args[0] == "AUTH_FAILURE"
            ]
            assert len(failure_calls) == 0


class TestVerifyApiKeyDirect:
    """Direct unit tests for verify_api_key function."""

    @pytest.mark.asyncio
    async def test_verify_api_key_returns_dev_mode_when_disabled(self) -> None:
        """verify_api_key should return 'dev-mode' when auth is disabled."""

        from unified_trading_api.middleware.auth import verify_api_key

        mock_request = MagicMock()
        mock_request.app.state.disable_auth = True
        mock_request.app.state.mock_mode = True

        result = await verify_api_key(mock_request, api_key=None)
        assert result == "dev-mode"

    @pytest.mark.asyncio
    async def test_verify_api_key_raises_401_without_key(self) -> None:
        """verify_api_key should raise 401 when key is missing and auth enabled."""
        from unified_trading_api.middleware.auth import verify_api_key

        mock_request = MagicMock()
        mock_request.app.state.disable_auth = False
        mock_request.app.state.mock_mode = False

        with patch("unified_trading_api.middleware.auth.log_event"):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(mock_request, api_key=None)
            assert exc_info.value.status_code == 401


class TestStandardLogging:
    """Verify standard Python logging is used in modules."""

    def test_main_module_has_logger(self) -> None:
        """main.py should define a module-level logger."""
        from unified_trading_api import main

        assert hasattr(main, "logger")
        assert main.logger.name == "unified_trading_api.main"

    def test_auth_module_has_logger(self) -> None:
        """auth.py should define a module-level logger."""
        from unified_trading_api.middleware import auth

        assert hasattr(auth, "logger")
        assert auth.logger.name == "unified_trading_api.middleware.auth"

    def test_state_store_has_logger(self) -> None:
        """state_store.py should define a module-level logger."""
        from unified_trading_api.mock_data import state_store

        assert hasattr(state_store, "logger")
        assert state_store.logger.name == "unified_trading_api.mock_data.state_store"

    def test_state_store_seed_logs_info(self) -> None:
        """MockStateStore.seed should log the domain and record count."""
        from unified_trading_api.mock_data.state_store import MockStateStore

        store = MockStateStore()
        with patch.object(store, "_data") as _:
            pass

        # Verify seed logs at INFO level
        import logging

        with patch.object(
            logging.getLogger("unified_trading_api.mock_data.state_store"), "info"
        ) as mock_info:
            store.seed("test_domain", [{"id": "1"}, {"id": "2"}])
            mock_info.assert_called_once_with("Seeded %s with %d records", "test_domain", 2)
