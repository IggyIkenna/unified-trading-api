"""Plan D Phase 2 — UTA subscribe/fork/approve/rollout endpoint smoke tests.

Covers feature-flag gating, exclusive-lock 409, fork 403-without-subscription,
approve 412-below-backtest-floor, and the happy-path
subscribe → fork → request-approval → approve → rollout loop.

Integration matrix (client-entitlement × subscription-type × Firestore paths)
is tracked as follow-up ``p2-uta-feature-flag-and-tests`` once the Firestore
store replaces the in-memory scaffold.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from unified_api_contracts.internal.domain.strategy_service.lifecycle import (  # noqa: qg-deep-import
    StrategyMaturityPhase,
)
from unified_api_contracts.strategy import SubscriptionType

from unified_trading_api.routes import strategy_subscriptions


def _client(admin: bool = True, feature_on: bool = True, tier: str = "enterprise") -> TestClient:
    """Minimal FastAPI app wiring the strategy_subscriptions router only.

    ``admin=True`` sets ``app.state.disable_auth = True`` so
    ``get_entitlement_context`` returns an INTERNAL org + enterprise tier
    (bypasses the entitlement gate). ``admin=False`` forces the non-bypass
    path by seeding JWT-like claims through ``request.state.auth_claims`` via
    a small middleware.
    """
    strategy_subscriptions.reset_stores_for_tests()
    app = FastAPI()
    app.state.feature_flags = {"dart_exclusive_enabled": feature_on}
    app.state.disable_auth = admin

    if not admin:
        # Seed auth claims on every request so get_entitlement_context resolves
        # to a non-internal org at the requested tier.
        @app.middleware("http")
        async def _seed_claims(request, call_next):  # pyright: ignore[reportUnknownParameterType,reportMissingParameterType]
            request.state.auth_claims = {
                "org_id": "client-foo",
                "org_type": "external",
                "tier": tier,
                "scoped_venues": [],
                "max_instruments": 100,
            }
            return await call_next(request)

    # Override verify_api_key to always pass.
    from unified_trading_api.middleware import auth as auth_mod

    app.dependency_overrides[auth_mod.verify_api_key] = lambda: None
    app.include_router(strategy_subscriptions.router, prefix="/api/v1")
    return TestClient(app)


def test_feature_flag_disabled_returns_404() -> None:
    client = _client(feature_on=False)
    resp = client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    assert resp.status_code == 404


def test_subscribe_happy_path() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["instance_id"] == "i_01"
    assert body["client_id"] == "c1"
    assert body["exclusive_lock"] is True
    assert body["subscription_type"] == "dart_exclusive"


def test_double_dart_exclusive_returns_409() -> None:
    client = _client()
    first = client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c2", "subscription_type": "dart_exclusive"},
    )
    assert second.status_code == 409
    assert "c1" in second.json()["detail"]
    assert "i_01" in second.json()["detail"]


def test_unsubscribe_then_resubscribe_works() -> None:
    client = _client()
    client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    rel = client.delete("/api/v1/strategy-instances/i_01/subscribe?client_id=c1")
    assert rel.status_code == 200
    again = client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c2", "subscription_type": "dart_exclusive"},
    )
    assert again.status_code == 201


def test_fork_requires_subscription() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/strategy-instances/i_01/fork",
        json={"client_id": "c1", "changed_fields": [], "unchanged_fingerprint": ""},
    )
    assert resp.status_code == 403


def test_approval_rejects_below_backtest_1yr() -> None:
    client = _client()
    # Subscribe + fork
    client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    fork_resp = client.post(
        "/api/v1/strategy-instances/i_01/fork",
        json={
            "client_id": "c1",
            "changed_fields": [("leverage", "2.0", "2.5")],
            "unchanged_fingerprint": "fp_abc",
        },
    )
    assert fork_resp.status_code == 201, fork_resp.text
    version_id = fork_resp.json()["version_id"]
    # Request approval
    req = client.post(f"/api/v1/strategy-versions/{version_id}/request-approval")
    assert req.status_code == 200
    # Approve with below-threshold backtest maturity
    below = client.post(
        f"/api/v1/strategy-versions/{version_id}/approve",
        json={
            "approved_by": "admin_iggy",
            "backtest_series_ref": "gs://x/y.parquet",
            "backtest_maturity": StrategyMaturityPhase.BACKTEST_MINIMAL.value,
        },
    )
    assert below.status_code == 412
    assert "backtest_maturity" in below.json()["detail"]


def test_full_subscribe_fork_approve_rollout_loop() -> None:
    client = _client()
    client.post(
        "/api/v1/strategy-instances/i_99/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    fork_resp = client.post(
        "/api/v1/strategy-instances/i_99/fork",
        json={
            "client_id": "c1",
            "changed_fields": [("leverage", "1.5", "2.0")],
            "unchanged_fingerprint": "fp_xyz",
        },
    )
    version_id = fork_resp.json()["version_id"]
    client.post(f"/api/v1/strategy-versions/{version_id}/request-approval")
    approve = client.post(
        f"/api/v1/strategy-versions/{version_id}/approve",
        json={
            "approved_by": "admin_iggy",
            "backtest_series_ref": "gs://x/y.parquet",
            "backtest_maturity": StrategyMaturityPhase.BACKTEST_1YR.value,
        },
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
    rollout = client.post(f"/api/v1/strategy-versions/{version_id}/rollout")
    assert rollout.status_code == 200
    assert rollout.json()["status"] == "rolled_out"


def test_reject_transitions_pending_to_rejected() -> None:
    client = _client()
    client.post(
        "/api/v1/strategy-instances/i_77/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    fork = client.post(
        "/api/v1/strategy-instances/i_77/fork",
        json={"client_id": "c1", "changed_fields": [], "unchanged_fingerprint": ""},
    )
    # Fork with no changed fields — the diff is empty but still a valid draft.
    version_id = fork.json()["version_id"]
    client.post(f"/api/v1/strategy-versions/{version_id}/request-approval")
    rej = client.post(
        f"/api/v1/strategy-versions/{version_id}/reject",
        json={"rejected_by": "admin_iggy", "rejection_reason": "insufficient alpha"},
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"


def test_non_admin_non_matching_tier_cannot_subscribe() -> None:
    # External org on 'basic' tier — neither strategy-full nor ml-full.
    client = _client(admin=False, tier="basic")
    resp = client.post(
        "/api/v1/strategy-instances/i_01/subscribe",
        json={"client_id": "c1", "subscription_type": "dart_exclusive"},
    )
    assert resp.status_code == 403
    assert "strategy-full" in resp.json()["detail"] or "ml-full" in resp.json()["detail"]


def _unused_imports_silencer() -> tuple[object, ...]:
    """Keep the import of ``SubscriptionType`` from being flagged unused."""
    return (SubscriptionType.DART_EXCLUSIVE,)
