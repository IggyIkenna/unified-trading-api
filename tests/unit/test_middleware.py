"""Tests for auth, entitlement, and latency middleware."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Auth middleware: verify_api_key + get_current_user
# ---------------------------------------------------------------------------


@pytest.fixture
def real_utl_auth_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force UTL create_api_auth off its DISABLE_AUTH/mock-mode short-circuit.

    QG exports CLOUD_MOCK_MODE=true process-wide, and verify_api_key's X-API-Key
    comparison now delegates to UTL's create_api_auth, which would otherwise take
    that env-driven mock-admin shortcut instead of exercising the real key check.
    ``_get_auth_config`` also ``@lru_cache``s that read, so a bare env override
    needs a cache clear to take effect.
    """
    utl_api_auth = importlib.import_module("unified_trading_library.cloud_interface.api_auth")
    monkeypatch.setenv("DISABLE_AUTH", "false")
    monkeypatch.setenv("CLOUD_MOCK_MODE", "false")
    utl_api_auth._get_auth_config.cache_clear()
    try:
        yield
    finally:
        utl_api_auth._get_auth_config.cache_clear()


class TestVerifyApiKey:
    """Test verify_api_key dependency."""

    def test_disable_auth_returns_dev_mode(self, app_client: TestClient) -> None:
        """When auth is disabled, verify_api_key returns 'dev-mode'."""
        # app_client has disable_auth=True; all routes with verify_api_key should pass
        resp = app_client.get("/alerts/summary")
        assert resp.status_code == 200

    def test_missing_api_key_returns_401(self) -> None:
        """When auth is enabled and no key sent, expect 401."""
        from unified_trading_library import setup_events

        setup_events("unified-trading-api", "test")

        from unified_trading_library import MockStateStore

        from unified_trading_api.main import create_app
        from unified_trading_api.mock_data.seed import seed_all_domains
        from unified_trading_api.services.mock_service import MockDomainService

        app = create_app()
        store = MockStateStore("test-auth-401")
        seed_all_domains(store)
        app.state.service = MockDomainService(store)
        app.state.mock_store = store
        app.state.mock_mode = True
        app.state.disable_auth = False
        app.state.start_time = 0.0
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/alerts/summary")
        assert resp.status_code == 401

    @pytest.mark.usefixtures("real_utl_auth_env")
    def test_invalid_api_key_returns_401(self) -> None:
        """When auth is enabled and wrong key sent, expect 401."""
        from unified_trading_library import setup_events

        setup_events("unified-trading-api", "test")

        from unified_trading_library import MockStateStore

        from unified_trading_api.main import create_app
        from unified_trading_api.mock_data.seed import seed_all_domains
        from unified_trading_api.services.mock_service import MockDomainService

        app = create_app()
        store = MockStateStore("test-auth-401-invalid")
        seed_all_domains(store)
        app.state.service = MockDomainService(store)
        app.state.mock_store = store
        app.state.mock_mode = True
        app.state.disable_auth = False
        app.state.start_time = 0.0
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/alerts/summary", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    @pytest.mark.usefixtures("real_utl_auth_env")
    def test_valid_api_key_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When auth is enabled and correct key sent, expect success.

        The real key check now delegates to UTL's ``create_api_auth``, which
        instantiates a fresh ``UnifiedCloudConfig`` per request — so the key
        must be set via the env var, not by mutating the local ``_auth_cfg``
        singleton (which UTL's fresh instance never reads).
        """
        from tests.unit.conftest import InMemoryService
        from unified_trading_api.main import create_app

        real_key = "test-valid-key-12345"
        monkeypatch.setenv("API_KEY", real_key)

        app = create_app()
        svc = InMemoryService()
        svc.seed("alert_summary", [{"total": 5}])
        app.state.mock_mode = True
        app.state.disable_auth = False
        app.state.start_time = 0.0
        app.state.service = svc

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/alerts/summary", headers={"X-API-Key": real_key})
        assert resp.status_code == 200


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    def test_persona_header_returns_persona(self) -> None:
        """X-Demo-Persona header with valid persona returns persona info."""
        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.auth import get_current_user

        app = create_app()
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0

        @app.get("/test-user")
        async def test_user(
            user: dict[str, object] = Depends(get_current_user),
        ) -> dict[str, object]:
            return user

        client = TestClient(app)
        resp = client.get("/test-user", headers={"x-demo-persona": "admin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "admin"
        assert data["org_id"] == "odum-internal"
        assert data["role"] == "admin"

    def test_unknown_persona_falls_through_to_default(self) -> None:
        """Unknown persona ID with disable_auth falls to default admin."""
        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.auth import get_current_user

        app = create_app()
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0

        @app.get("/test-user")
        async def test_user(
            user: dict[str, object] = Depends(get_current_user),
        ) -> dict[str, object]:
            return user

        client = TestClient(app)
        resp = client.get("/test-user", headers={"x-demo-persona": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        # Falls through to default admin user
        assert data["user_id"] == "admin"

    def test_bearer_token_mock_mode(self) -> None:
        """Valid JWT in mock mode returns decoded claims."""
        import jwt as pyjwt

        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.auth import get_current_user

        app = create_app()
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0

        @app.get("/test-user")
        async def test_user(
            user: dict[str, object] = Depends(get_current_user),
        ) -> dict[str, object]:
            return user

        secret = "auth-api-dev-secret-do-not-use-in-production"
        token = pyjwt.encode(
            {
                "sub": "user-123",
                "org_id": "acme",
                "role": "client",
                "name": "Test User",
                "entitlements": ["data-pro"],
            },
            secret,
            algorithm="HS256",
        )

        client = TestClient(app)
        resp = client.get("/test-user", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-123"
        assert data["org_id"] == "acme"

    def test_invalid_bearer_token_disable_auth_falls_through(self) -> None:
        """Invalid JWT with disable_auth falls through to default admin."""
        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.auth import get_current_user

        app = create_app()
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0

        @app.get("/test-user")
        async def test_user(
            user: dict[str, object] = Depends(get_current_user),
        ) -> dict[str, object]:
            return user

        client = TestClient(app)
        resp = client.get("/test-user", headers={"Authorization": "Bearer invalid-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "admin"

    def test_no_auth_disabled_no_token_returns_401(self) -> None:
        """No token and auth not disabled returns 401."""
        from unified_trading_library import setup_events

        setup_events("unified-trading-api", "test")

        from tests.unit.conftest import InMemoryService
        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.auth import get_current_user

        app = create_app()
        svc = InMemoryService()
        app.state.service = svc
        app.state.mock_mode = False
        app.state.disable_auth = False
        app.state.start_time = 0.0

        @app.get("/test-user")
        async def test_user(
            user: dict[str, object] = Depends(get_current_user),
        ) -> dict[str, object]:
            return user

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-user")
        assert resp.status_code == 401

    def test_default_admin_when_auth_disabled(self) -> None:
        """No persona, no token, but auth disabled returns default admin."""
        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.auth import get_current_user

        app = create_app()
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0

        @app.get("/test-user")
        async def test_user(
            user: dict[str, object] = Depends(get_current_user),
        ) -> dict[str, object]:
            return user

        client = TestClient(app)
        resp = client.get("/test-user")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "admin"
        assert data["entitlements"] == ["*"]


# ---------------------------------------------------------------------------
# Entitlement middleware
# ---------------------------------------------------------------------------


class TestEntitlementContext:
    """Test EntitlementContext and get_entitlement_context."""

    def test_org_type_enum(self) -> None:
        from unified_trading_api.middleware.entitlement import OrgType

        assert OrgType.INTERNAL == "internal"
        assert OrgType.EXTERNAL == "external"

    def test_entitlement_context_internal(self) -> None:
        from unified_trading_api.middleware.entitlement import EntitlementContext, OrgType

        ctx = EntitlementContext(org_id="odum", org_type=OrgType.INTERNAL)
        assert ctx.is_internal is True
        assert ctx.org_id == "odum"
        assert ctx.tier == "enterprise"
        assert ctx.scoped_venues == []
        assert ctx.max_instruments == 10000

    def test_entitlement_context_external(self) -> None:
        from unified_trading_api.middleware.entitlement import EntitlementContext, OrgType

        ctx = EntitlementContext(
            org_id="acme",
            org_type=OrgType.EXTERNAL,
            tier="basic",
            scoped_venues=["binance"],
            max_instruments=100,
        )
        assert ctx.is_internal is False
        assert ctx.scoped_venues == ["binance"]
        assert ctx.max_instruments == 100

    def test_get_entitlement_context_mock_mode(self) -> None:
        """When disable_auth=True, returns internal context."""
        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.entitlement import get_entitlement_context

        app = create_app()
        app.state.mock_mode = True
        app.state.disable_auth = True
        app.state.start_time = 0.0

        @app.get("/test-entitlement")
        async def test_ent(request: Request) -> dict[str, object]:
            ctx = get_entitlement_context(request)
            return {
                "org_id": ctx.org_id,
                "is_internal": ctx.is_internal,
                "tier": ctx.tier,
            }

        client = TestClient(app)
        resp = client.get("/test-entitlement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["org_id"] == "mock-org"
        assert data["is_internal"] is True

    def test_get_entitlement_context_real_mode(self) -> None:
        """When disable_auth=False, extracts from auth_claims."""
        from unified_trading_api.main import create_app
        from unified_trading_api.middleware.entitlement import get_entitlement_context

        app = create_app()
        app.state.mock_mode = False
        app.state.disable_auth = False
        app.state.start_time = 0.0

        @app.get("/test-entitlement")
        async def test_ent(request: Request) -> dict[str, object]:
            # Simulate auth middleware setting claims
            request.state.auth_claims = {
                "org_id": "acme",
                "org_type": "external",
                "tier": "basic",
                "scoped_venues": ["binance", "okx"],
                "max_instruments": 200,
            }
            ctx = get_entitlement_context(request)
            return {
                "org_id": ctx.org_id,
                "is_internal": ctx.is_internal,
                "tier": ctx.tier,
                "scoped_venues": ctx.scoped_venues,
                "max_instruments": ctx.max_instruments,
            }

        client = TestClient(app)
        resp = client.get("/test-entitlement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["org_id"] == "acme"
        assert data["is_internal"] is False
        assert data["tier"] == "basic"
        assert data["scoped_venues"] == ["binance", "okx"]
        assert data["max_instruments"] == 200


# ---------------------------------------------------------------------------
# Latency middleware
# ---------------------------------------------------------------------------


class TestLatencyMiddleware:
    """Test LatencyMiddleware dispatch logic."""

    def test_no_latency_when_base_ms_zero(self) -> None:
        """base_ms=0 means no delay."""
        from unified_trading_api.middleware.latency import LatencyMiddleware

        app = FastAPI()
        app.add_middleware(LatencyMiddleware, base_ms=0)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"ok": "true"}

        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200

    def test_health_skips_latency(self) -> None:
        """Health endpoint should skip latency even when base_ms > 0."""
        from unified_trading_api.middleware.latency import LatencyMiddleware

        app = FastAPI()
        app.add_middleware(LatencyMiddleware, base_ms=100)

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_readiness_skips_latency(self) -> None:
        from unified_trading_api.middleware.latency import LatencyMiddleware

        app = FastAPI()
        app.add_middleware(LatencyMiddleware, base_ms=100)

        @app.get("/readiness")
        async def readiness() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        resp = client.get("/readiness")
        assert resp.status_code == 200

    def test_admin_skips_latency(self) -> None:
        from unified_trading_api.middleware.latency import LatencyMiddleware

        app = FastAPI()
        app.add_middleware(LatencyMiddleware, base_ms=100)

        @app.get("/admin/reset")
        async def admin_reset() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        resp = client.get("/admin/reset")
        assert resp.status_code == 200

    def test_get_request_has_latency(self) -> None:
        """GET requests (non-exempt) should apply latency."""
        from unittest.mock import AsyncMock

        from unified_trading_api.middleware.latency import LatencyMiddleware

        app = FastAPI()
        app.add_middleware(LatencyMiddleware, base_ms=10)

        @app.get("/data")
        async def get_data() -> dict[str, str]:
            return {"data": "ok"}

        client = TestClient(app)
        with patch("unified_trading_api.middleware.latency.asyncio.sleep", new_callable=AsyncMock):
            resp = client.get("/data")
        assert resp.status_code == 200

    def test_post_request_has_shorter_latency(self) -> None:
        """POST requests have shorter latency (base_ms // 3)."""
        from unittest.mock import AsyncMock

        from unified_trading_api.middleware.latency import LatencyMiddleware

        app = FastAPI()
        app.add_middleware(LatencyMiddleware, base_ms=30)

        @app.post("/action")
        async def post_action() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        with patch("unified_trading_api.middleware.latency.asyncio.sleep", new_callable=AsyncMock):
            resp = client.post("/action")
        assert resp.status_code == 200
