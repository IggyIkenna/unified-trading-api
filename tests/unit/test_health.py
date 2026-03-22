"""Tests for health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create test client with mock mode."""
    from unified_trading_api.main import create_app

    app = create_app()
    app.state.mock_mode = True
    app.state.disable_auth = True
    app.state.start_time = 0.0
    return TestClient(app)


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


def test_readiness_returns_200(client: TestClient) -> None:
    response = client.get("/readiness")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_mock_mode_returns_mock_state_store(client: TestClient) -> None:
    """In mock mode (Tier 1), upstream_checks includes the mock-state-store entry."""
    response = client.get("/readiness")
    assert response.status_code == 200
    data = response.json()

    assert data["mock_mode"] is True
    assert data["declared_runtime_tier"] == 1

    checks = data["upstream_checks"]
    assert len(checks) == 1
    store_check = checks[0]
    assert store_check["name"] == "mock-state-store"
    assert store_check["required_for_tier"] == 1
    assert store_check["ok"] is True
    assert store_check["url"] == "in-process"
