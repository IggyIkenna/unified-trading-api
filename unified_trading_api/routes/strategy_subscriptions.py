# SCHEMA_PROVENANCE_EXEMPT — request DTOs are HTTP transport wrappers only.
"""Plan D Phase 2 — DART exclusive subscription + research-fork + version-governance endpoints.

Seven endpoints, all feature-flagged behind ``dart_exclusive_enabled``:

- ``POST   /api/v1/strategy-instances/{instance_id}/subscribe``
- ``DELETE /api/v1/strategy-instances/{instance_id}/subscribe``
- ``POST   /api/v1/strategy-instances/{instance_id}/fork``
- ``POST   /api/v1/strategy-versions/{version_id}/request-approval``
- ``POST   /api/v1/strategy-versions/{version_id}/approve``
- ``POST   /api/v1/strategy-versions/{version_id}/reject``
- ``POST   /api/v1/strategy-versions/{version_id}/rollout``

Backend store: in-memory ``_SubscriptionStore`` + ``_VersionStore`` for now.
Production swap-in: Firestore ``strategy_instance_subscriptions`` +
``strategy_versions`` collections (tracked as Plan D Phase 2 follow-up
``p2-firestore-migration``).

Events emitted via ``unified_trading_library.events`` (see UTL commit
``797f1f99``).

SSOT:
    - plans/active/dart_exclusive_subscription_research_fork_2026_04_21.md
    - UAC ``unified_api_contracts.strategy`` — SubscriptionType,
      StrategyInstanceSubscription, VersionStatus, StrategyVersion,
      ApprovalRecord, ConfigDiff, ExclusiveLockViolation,
      minimum_approval_maturity.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from unified_api_contracts.internal.domain.strategy_service.lifecycle import (  # noqa: qg-deep-import — internal facade
    StrategyMaturityPhase,
    maturity_phase_rank,
)
from unified_api_contracts.strategy import (
    ApprovalRecord,
    ConfigDiff,
    ExclusiveLockViolation,
    StrategyInstanceSubscription,
    StrategyVersion,
    SubscriptionType,
    VersionStatus,
    minimum_approval_maturity,
)

# Plan D Phase 3 — event emissions on subscription / version state changes.
# Wrapped in a defensive helper because the events module raises
# RuntimeError when ``setup_events()`` has not been called (e.g. unit tests
# that bypass the FastAPI lifespan startup). UTA prod startup wires
# ``setup_events`` so the live path always emits.
from unified_trading_library import log_event as _log_event_unsafe

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,
)
from unified_trading_api.middleware.entitlement import (  # noqa: qg-deep-import — self-package
    get_entitlement_context,
)

logger = logging.getLogger(__name__)


def _safe_log_event(name: str, details: dict[str, str]) -> None:
    try:
        details_obj: dict[str, object] = dict(details)
        _log_event_unsafe(name, details=details_obj)
    except RuntimeError:
        logger.info("event-emit-skipped (events not initialised) name=%s", name)


# ─── Feature flag ───────────────────────────────────────────────────────
# Default OFF during Plan D Phase 2 scaffold. Flip to True via env in
# staging once Phase 3 strategy-service worker + Phase 4 UI land.
_DART_EXCLUSIVE_ENABLED_DEFAULT = False


def _feature_enabled(request: Request) -> bool:
    app_state: dict[str, bool] = cast(
        dict[str, bool],
        getattr(request.app.state, "feature_flags", {}),  # pyright: ignore[reportAny]
    )
    flag = app_state.get("dart_exclusive_enabled", _DART_EXCLUSIVE_ENABLED_DEFAULT)
    return bool(flag)


def _require_feature(request: Request) -> None:
    if not _feature_enabled(request):
        raise HTTPException(status_code=404, detail="dart_exclusive endpoints disabled")


# ─── In-memory stores (Firestore swap-in pending) ───────────────────────


class _SubscriptionStore:
    """Thread-safe in-memory subscription registry.

    Lifetime scoped to the UTA process. Production replaces this with a
    Firestore-backed repo keyed on (instance_id, client_id, subscribed_at).
    """

    def __init__(self) -> None:
        self._by_key: dict[str, StrategyInstanceSubscription] = {}
        self._lock = Lock()

    @staticmethod
    def _key(instance_id: str, client_id: str, subscribed_at: datetime) -> str:
        return f"{instance_id}::{client_id}::{subscribed_at.isoformat()}"

    def active_exclusive(self, instance_id: str) -> StrategyInstanceSubscription | None:
        with self._lock:
            for sub in self._by_key.values():
                if sub.instance_id == instance_id and sub.exclusive_lock and sub.released_at is None:
                    return sub
        return None

    def create(self, sub: StrategyInstanceSubscription) -> StrategyInstanceSubscription:
        with self._lock:
            if sub.subscription_type is SubscriptionType.DART_EXCLUSIVE:
                existing = self._active_exclusive_locked(sub.instance_id)
                if existing is not None:
                    raise ExclusiveLockViolation(
                        existing_holder=existing.client_id,
                        instance_id=sub.instance_id,
                    )
            key = self._key(sub.instance_id, sub.client_id, sub.subscribed_at)
            self._by_key[key] = sub
            return sub

    def _active_exclusive_locked(self, instance_id: str) -> StrategyInstanceSubscription | None:
        for sub in self._by_key.values():
            if sub.instance_id == instance_id and sub.exclusive_lock and sub.released_at is None:
                return sub
        return None

    def release_exclusive(
        self, instance_id: str, client_id: str, released_at: datetime
    ) -> StrategyInstanceSubscription | None:
        with self._lock:
            target_key: str | None = None
            target: StrategyInstanceSubscription | None = None
            for key, sub in self._by_key.items():
                if (
                    sub.instance_id == instance_id
                    and sub.client_id == client_id
                    and sub.subscription_type is SubscriptionType.DART_EXCLUSIVE
                    and sub.released_at is None
                ):
                    target_key, target = key, sub
                    break
            if target is None or target_key is None:
                return None
            released = StrategyInstanceSubscription(
                instance_id=target.instance_id,
                client_id=target.client_id,
                subscription_type=target.subscription_type,
                subscribed_at=target.subscribed_at,
                released_at=released_at,
                exclusive_lock=False,
                version_id=target.version_id,
                fork_lineage=target.fork_lineage,
                notes=target.notes,
            )
            self._by_key[target_key] = released
            return released

    def reset_for_tests(self) -> None:
        with self._lock:
            self._by_key.clear()


class _VersionStore:
    """Thread-safe in-memory version registry."""

    def __init__(self) -> None:
        self._by_id: dict[str, StrategyVersion] = {}
        self._lock = Lock()

    def get(self, version_id: str) -> StrategyVersion | None:
        with self._lock:
            return self._by_id.get(version_id)

    def put(self, version: StrategyVersion) -> StrategyVersion:
        with self._lock:
            self._by_id[version.version_id] = version
            return version

    def active_for_instance(self, instance_id: str) -> StrategyVersion | None:
        with self._lock:
            for version in self._by_id.values():
                if version.parent_instance_id == instance_id and version.status is VersionStatus.ROLLED_OUT:
                    return version
        return None

    def reset_for_tests(self) -> None:
        with self._lock:
            self._by_id.clear()


_subscription_store = _SubscriptionStore()
_version_store = _VersionStore()


def _get_subscription_store() -> _SubscriptionStore:
    return _subscription_store


def _get_version_store() -> _VersionStore:
    return _version_store


# ─── Request / response DTOs (HTTP transport only) ──────────────────────


class SubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(min_length=1)
    subscription_type: SubscriptionType


class SubscribeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_id: str
    client_id: str
    subscription_type: str
    subscribed_at: str
    version_id: str
    exclusive_lock: bool


class UnsubscribeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_id: str
    client_id: str
    released_at: str


class ForkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(min_length=1)
    changed_fields: list[tuple[str, str, str]] = Field(default_factory=list)
    unchanged_fingerprint: str = Field(default="")


class VersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str
    parent_instance_id: str
    parent_version_id: str | None
    maturity_phase: str
    status: str
    authored_by: str


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved_by: str = Field(min_length=1)
    backtest_series_ref: str = Field(min_length=1)
    backtest_maturity: StrategyMaturityPhase
    review_notes: str | None = None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rejected_by: str = Field(min_length=1)
    rejection_reason: str = Field(min_length=1)


# ─── Entitlement helpers ────────────────────────────────────────────────


_SUBSCRIPTION_ENTITLEMENTS: dict[SubscriptionType, frozenset[str]] = {
    SubscriptionType.DART_EXCLUSIVE: frozenset({"strategy-full", "ml-full"}),
    SubscriptionType.IM_ALLOCATION: frozenset({"im-client", "reporting"}),
    SubscriptionType.SIGNALS_IN: frozenset({"execution-full"}),
}


def _check_subscription_entitlement(request: Request, subscription_type: SubscriptionType) -> None:
    ctx = get_entitlement_context(request)
    if ctx.is_internal:
        return
    required = _SUBSCRIPTION_ENTITLEMENTS[subscription_type]
    if ctx.tier in required:
        return
    logger.info(
        "subscribe 403 org=%s tier=%s type=%s (requires one of %s)",
        ctx.org_id,
        ctx.tier,
        subscription_type.value,
        sorted(required),
    )
    raise HTTPException(
        status_code=403,
        detail=(
            f"Subscription type {subscription_type.value} requires one of {sorted(required)}; current tier={ctx.tier}."
        ),
    )


def _require_admin(request: Request) -> None:
    ctx = get_entitlement_context(request)
    if not ctx.is_internal:
        raise HTTPException(status_code=403, detail="Admin role required.")


# ─── Router ──────────────────────────────────────────────────────────────


router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post(
    "/strategy-instances/{instance_id}/subscribe",
    response_model=SubscribeResponse,
    status_code=201,
)
def subscribe(
    instance_id: str,
    payload: SubscribeRequest,
    request: Request,
    store: _SubscriptionStore = Depends(_get_subscription_store),
    versions: _VersionStore = Depends(_get_version_store),
) -> SubscribeResponse:
    _require_feature(request)
    _check_subscription_entitlement(request, payload.subscription_type)
    now = datetime.now(UTC)
    active_version = versions.active_for_instance(instance_id)
    version_id = active_version.version_id if active_version else _genesis_version_id(instance_id)
    if active_version is None:
        # Create an implicit genesis version record so downstream fork flows
        # have a parent to point at. ``live_stable`` is used as the initial
        # phase because this represents the catalogue's shipped configuration
        # — drafts start fresh at smoke.
        genesis = StrategyVersion(
            version_id=version_id,
            parent_instance_id=instance_id,
            maturity_phase=StrategyMaturityPhase.LIVE_STABLE,
            status=VersionStatus.ROLLED_OUT,
            authored_by="system_seed",
            created_at=now,
            rolled_out_at=now,
            approval=ApprovalRecord(
                approved_by="system_seed",
                approved_at=now,
                backtest_maturity=StrategyMaturityPhase.LIVE_STABLE,
                backtest_series_ref="seed://genesis",
            ),
        )
        versions.put(genesis)
    sub = StrategyInstanceSubscription(
        instance_id=instance_id,
        client_id=payload.client_id,
        subscription_type=payload.subscription_type,
        subscribed_at=now,
        version_id=version_id,
        fork_lineage=(version_id,),
        exclusive_lock=payload.subscription_type is SubscriptionType.DART_EXCLUSIVE,
    )
    try:
        created = store.create(sub)
    except ExclusiveLockViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _safe_log_event(
        "STRATEGY_SUBSCRIPTION_CREATED",
        {
            "instance_id": created.instance_id,
            "client_id": created.client_id,
            "subscription_type": created.subscription_type.value,
            "exclusive_lock": str(created.exclusive_lock),
        },
    )
    logger.info(
        "subscribe created instance=%s client=%s type=%s",
        created.instance_id,
        created.client_id,
        created.subscription_type.value,
    )
    return SubscribeResponse(
        instance_id=created.instance_id,
        client_id=created.client_id,
        subscription_type=created.subscription_type.value,
        subscribed_at=created.subscribed_at.isoformat(),
        version_id=created.version_id,
        exclusive_lock=created.exclusive_lock,
    )


@router.delete(
    "/strategy-instances/{instance_id}/subscribe",
    response_model=UnsubscribeResponse,
)
def unsubscribe(
    instance_id: str,
    request: Request,
    client_id: str = Query(..., min_length=1),
    store: _SubscriptionStore = Depends(_get_subscription_store),
) -> UnsubscribeResponse:
    _require_feature(request)
    now = datetime.now(UTC)
    released = store.release_exclusive(instance_id, client_id, now)
    if released is None:
        raise HTTPException(
            status_code=404,
            detail=(f"No active DART_EXCLUSIVE subscription for instance_id={instance_id} client_id={client_id}."),
        )
    _safe_log_event(
        "STRATEGY_SUBSCRIPTION_RELEASED",
        {
            "instance_id": released.instance_id,
            "client_id": released.client_id,
            "reason": "client_unsubscribed",
        },
    )
    logger.info("unsubscribe instance=%s client=%s", instance_id, client_id)
    assert released.released_at is not None
    return UnsubscribeResponse(
        instance_id=released.instance_id,
        client_id=released.client_id,
        released_at=released.released_at.isoformat(),
    )


@router.post(
    "/strategy-instances/{instance_id}/fork",
    response_model=VersionResponse,
    status_code=201,
)
def fork(
    instance_id: str,
    payload: ForkRequest,
    request: Request,
    store: _SubscriptionStore = Depends(_get_subscription_store),
    versions: _VersionStore = Depends(_get_version_store),
) -> VersionResponse:
    _require_feature(request)
    active = store.active_exclusive(instance_id)
    if active is None or active.client_id != payload.client_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Fork requires an active DART_EXCLUSIVE subscription held by "
                f"client_id={payload.client_id} on instance_id={instance_id}."
            ),
        )
    parent = versions.active_for_instance(instance_id)
    if parent is None:
        raise HTTPException(
            status_code=409,
            detail=f"instance_id={instance_id} has no active rolled-out version to fork.",
        )
    now = datetime.now(UTC)
    version_id = f"v_{uuid.uuid4().hex[:12]}"
    diff = ConfigDiff(
        base_version_id=parent.version_id,
        changed_fields=tuple(payload.changed_fields),
        unchanged_fingerprint=payload.unchanged_fingerprint,
    )
    draft = StrategyVersion(
        version_id=version_id,
        parent_instance_id=instance_id,
        maturity_phase=StrategyMaturityPhase.SMOKE,
        status=VersionStatus.DRAFT,
        authored_by=payload.client_id,
        created_at=now,
        parent_version_id=parent.version_id,
        config_diff=diff,
    )
    versions.put(draft)
    _safe_log_event(
        "STRATEGY_VERSION_DRAFT_CREATED",
        {
            "version_id": draft.version_id,
            "parent_instance_id": draft.parent_instance_id,
            "parent_version_id": parent.version_id,
            "authored_by": payload.client_id,
        },
    )
    logger.info(
        "version draft created version_id=%s parent=%s author=%s",
        draft.version_id,
        parent.version_id,
        payload.client_id,
    )
    return _version_response(draft)


@router.post(
    "/strategy-versions/{version_id}/request-approval",
    response_model=VersionResponse,
)
def request_approval(
    version_id: str,
    request: Request,
    versions: _VersionStore = Depends(_get_version_store),
) -> VersionResponse:
    _require_feature(request)
    version = versions.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"version_id={version_id} not found")
    if version.status is not VersionStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail=f"version_id={version_id} is {version.status.value}; only DRAFT → PENDING_APPROVAL.",
        )
    updated = _replace_version(version, status=VersionStatus.PENDING_APPROVAL)
    versions.put(updated)
    _safe_log_event(
        "STRATEGY_VERSION_APPROVAL_REQUESTED",
        {
            "version_id": updated.version_id,
            "instance_id": updated.parent_instance_id,
            "authored_by": updated.authored_by,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )
    logger.info("version approval requested version_id=%s", version_id)
    return _version_response(updated)


@router.post(
    "/strategy-versions/{version_id}/approve",
    response_model=VersionResponse,
)
def approve(
    version_id: str,
    payload: ApproveRequest,
    request: Request,
    versions: _VersionStore = Depends(_get_version_store),
) -> VersionResponse:
    _require_feature(request)
    _require_admin(request)
    version = versions.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"version_id={version_id} not found")
    if version.status is not VersionStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"version_id={version_id} is {version.status.value}; only PENDING_APPROVAL → APPROVED.",
        )
    min_phase = minimum_approval_maturity()
    if maturity_phase_rank(payload.backtest_maturity) < maturity_phase_rank(min_phase):
        raise HTTPException(
            status_code=412,
            detail=(
                f"Approval requires backtest_maturity >= {min_phase.value}; got {payload.backtest_maturity.value}."
            ),
        )
    now = datetime.now(UTC)
    approval = ApprovalRecord(
        approved_by=payload.approved_by,
        approved_at=now,
        backtest_maturity=payload.backtest_maturity,
        backtest_series_ref=payload.backtest_series_ref,
        review_notes=payload.review_notes,
    )
    updated = _replace_version(
        version,
        status=VersionStatus.APPROVED,
        approval=approval,
        backtest_series_ref=payload.backtest_series_ref,
        maturity_phase=payload.backtest_maturity,
    )
    versions.put(updated)
    _safe_log_event(
        "STRATEGY_VERSION_APPROVED",
        {
            "version_id": updated.version_id,
            "approved_by": payload.approved_by,
            "backtest_maturity": payload.backtest_maturity.value,
            "backtest_series_ref": payload.backtest_series_ref,
        },
    )
    logger.info(
        "version approved version_id=%s approver=%s maturity=%s",
        version_id,
        payload.approved_by,
        payload.backtest_maturity.value,
    )
    return _version_response(updated)


@router.post(
    "/strategy-versions/{version_id}/reject",
    response_model=VersionResponse,
)
def reject(
    version_id: str,
    payload: RejectRequest,
    request: Request,
    versions: _VersionStore = Depends(_get_version_store),
) -> VersionResponse:
    _require_feature(request)
    _require_admin(request)
    version = versions.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"version_id={version_id} not found")
    if version.status is not VersionStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"version_id={version_id} is {version.status.value}; only PENDING_APPROVAL → REJECTED.",
        )
    updated = _replace_version(version, status=VersionStatus.REJECTED)
    versions.put(updated)
    _safe_log_event(
        "STRATEGY_VERSION_REJECTED",
        {
            "version_id": updated.version_id,
            "rejected_by": payload.rejected_by,
            "rejection_reason": payload.rejection_reason,
        },
    )
    logger.info(
        "version rejected version_id=%s rejector=%s reason=%s",
        version_id,
        payload.rejected_by,
        payload.rejection_reason,
    )
    return _version_response(updated)


@router.post(
    "/strategy-versions/{version_id}/rollout",
    response_model=VersionResponse,
)
def rollout(
    version_id: str,
    request: Request,
    versions: _VersionStore = Depends(_get_version_store),
) -> VersionResponse:
    _require_feature(request)
    _require_admin(request)
    version = versions.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"version_id={version_id} not found")
    if version.status is not VersionStatus.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"version_id={version_id} is {version.status.value}; only APPROVED → ROLLED_OUT.",
        )
    now = datetime.now(UTC)
    prior = versions.active_for_instance(version.parent_instance_id)
    updated = _replace_version(
        version,
        status=VersionStatus.ROLLED_OUT,
        rolled_out_at=now,
        supersedes_version_id=prior.version_id if prior is not None else None,
    )
    versions.put(updated)
    if prior is not None and prior.version_id != updated.version_id:
        retired = _replace_version(prior, status=VersionStatus.RETIRED)
        versions.put(retired)
    _safe_log_event(
        "STRATEGY_VERSION_ROLLED_OUT",
        {
            "version_id": updated.version_id,
            "instance_id": updated.parent_instance_id,
            "supersedes_version_id": prior.version_id if prior is not None else "",
            "rolled_out_at": now.isoformat(),
        },
    )
    logger.info(
        "version rolled out version_id=%s instance=%s supersedes=%s",
        version_id,
        version.parent_instance_id,
        prior.version_id if prior is not None else "(none)",
    )
    return _version_response(updated)


# ─── Helpers ─────────────────────────────────────────────────────────────


def _genesis_version_id(instance_id: str) -> str:
    return f"v_genesis_{instance_id[:16]}"


def _version_response(v: StrategyVersion) -> VersionResponse:
    return VersionResponse(
        version_id=v.version_id,
        parent_instance_id=v.parent_instance_id,
        parent_version_id=v.parent_version_id,
        maturity_phase=v.maturity_phase.value,
        status=v.status.value,
        authored_by=v.authored_by,
    )


def _replace_version(
    v: StrategyVersion,
    **overrides: object,
) -> StrategyVersion:
    """Dataclass-flavoured ``replace`` helper. Keeps call sites compact."""
    fields: dict[str, object] = {
        "version_id": v.version_id,
        "parent_instance_id": v.parent_instance_id,
        "maturity_phase": v.maturity_phase,
        "status": v.status,
        "authored_by": v.authored_by,
        "created_at": v.created_at,
        "parent_version_id": v.parent_version_id,
        "config_diff": v.config_diff,
        "backtest_series_ref": v.backtest_series_ref,
        "approval": v.approval,
        "rolled_out_at": v.rolled_out_at,
        "supersedes_version_id": v.supersedes_version_id,
        "review_history": v.review_history,
    }
    fields.update(overrides)
    return StrategyVersion(**fields)  # pyright: ignore[reportArgumentType]


def reset_stores_for_tests() -> None:
    """Test hook — flush the in-memory state."""
    _subscription_store.reset_for_tests()
    _version_store.reset_for_tests()


def set_feature_flag_for_tests(app_state_setter: Callable[[dict[str, bool]], None], enabled: bool) -> None:
    """Test hook — toggle the feature flag via app state."""
    app_state_setter({"dart_exclusive_enabled": enabled})
