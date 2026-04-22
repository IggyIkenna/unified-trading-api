# SCHEMA_PROVENANCE_EXEMPT — response DTOs here are HTTP transport wrappers only.
"""Strategy-instance performance series — Plan C endpoint.

SSOT: ``unified-trading-pm/codex/09-strategy/architecture-v2/performance-overlay.md``.

Endpoint
--------

``GET /api/v1/strategy-instances/{instance_id}/performance``
    Returns the continuous backtest / paper / live P&L timeline for a
    single strategy instance. Three colour-coded series back the
    ``<PerformanceOverlay>`` UI component (Plan C) on FOMO tearsheets,
    the DART terminal Performance tab, and the Reports IM allocator
    subsection.

Source of truth
---------------

Both the paper + live series are sourced from the ``odum-paper`` /
``odum-live`` client-zero representative-account runs (see
``memory/project_odum_paper_client_zero_representative_account_2026_04_21.md``)
— the "live" line on FOMO tearsheets is always Odum's own live run,
never a real client's flow.

Runtime source resolution:

1. Attempts a real query against position-balance-monitor-service via
   :class:`PbmPerformanceClient` (HTTP; endpoint contract declared below).
2. Falls back to the deterministic synthesiser when PBM is unavailable,
   returns 404 (instance not yet onboarded to odum-paper), or when running
   in mock mode (``CLOUD_MOCK_MODE=true``).

PBM endpoint contract (prereq follow-up — see Plan C p1-pbm-endpoint-delivery):
    ``GET <pbm>/api/v1/accounts/{account_id}/pnl-series``
    Query: ``instance_id`` (required), ``from`` (ISO-8601 or ``Nd`` rolling),
    ``to`` (ISO-8601 or ``now``), ``per_venue`` (bool).
    Returns the same shape as :class:`_PerViewSeries`.

Plan C p1-pbm-wiring-followup closure (2026-04-22): entitlement gate + typed
PBM adapter with fallback shipped. PBM endpoint itself is a separate PBM-repo
follow-up (Plan C p1-pbm-endpoint-delivery).

Permissioning
-------------

Two alternative gates (OR):

- ``reporting`` entitlement — grants access to all instances routed
  ``dart_only|im_only|both`` (FOMO surface path).
- Subscription row on ``(org, instance_id)`` — grants access even
  without the ``reporting`` entitlement (Reality surface path).

Admin + internal-trader bypass both gates.

SCHEMA_PROVENANCE_EXEMPT: response DTOs are the HTTP transport shape for
this endpoint — the canonical domain types (``StrategyMaturityPhase``,
``AccountType``) live in UAC and are used as-is for ``phase_annotations``
enum values.
"""

# SCHEMA_PROVENANCE_EXEMPT — see module docstring above.

from __future__ import annotations

import hashlib
import logging
import math
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.middleware.entitlement import (  # noqa: qg-deep-import — self-package
    get_entitlement_context,  # noqa: qg-deep-import — self-package
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

# ─── Cache TTLs (per §4 of performance-overlay.md) ──────────────────────
_PAPER_LIVE_TTL_S = 60.0
_BACKTEST_TTL_S = 3600.0

_Views = tuple[str, ...]
_VALID_VIEWS: frozenset[str] = frozenset({"backtest", "paper", "live"})


class _SeriesPoint(BaseModel):  # CORRECT-LOCAL: UTA performance transport
    model_config = ConfigDict(extra="forbid")

    t: str = Field(description="ISO-8601 UTC timestamp for this sample.")
    pnl: float = Field(description="Cumulative P&L at this point in USD.")
    equity: float = Field(description="Equity curve level at this point in USD.")


class _TransitionMarkers(BaseModel):  # CORRECT-LOCAL: UTA performance transport
    model_config = ConfigDict(extra="forbid")

    paper_started_at: str | None = Field(default=None)
    live_started_at: str | None = Field(default=None)


class _PhaseAnnotation(BaseModel):  # CORRECT-LOCAL: UTA performance transport
    model_config = ConfigDict(extra="forbid")

    phase: str = Field(description="UAC StrategyMaturityPhase enum value.")
    at: str = Field(description="ISO-8601 UTC timestamp of the transition.")


class _PerViewSeries(BaseModel):  # CORRECT-LOCAL: UTA performance transport
    model_config = ConfigDict(extra="forbid")

    aggregate: list[_SeriesPoint] = Field(default_factory=list)
    per_venue: dict[str, list[_SeriesPoint]] | None = Field(default=None)


class PerformanceSeriesResponse(BaseModel):  # CORRECT-LOCAL: UTA performance transport
    """GET response shape. Mirrors performance-overlay.md §4."""

    model_config = ConfigDict(extra="forbid")

    instance_id: str
    series: dict[str, _PerViewSeries] = Field(
        description="Per-view series keyed on 'backtest' | 'paper' | 'live'."
    )
    transition_markers: _TransitionMarkers
    phase_annotations: list[_PhaseAnnotation]


# ─── PBM adapter (Plan C p1-pbm-wiring-followup) ────────────────────────
#
# The UTA side of the Plan C wire is in place: an entitlement gate +
# a typed PBM-client adapter with fallback to deterministic synthesis.
#
# The real PBM ``/api/v1/accounts/{account_id}/pnl-series`` endpoint is a
# separate position-balance-monitor-service delivery tracked as Plan C
# follow-up todo ``p1-pbm-endpoint-delivery``. When PBM ships that route,
# wire ``HttpPbmPerformanceClient`` against it and remove the
# ``CLOUD_MOCK_MODE`` short-circuit below.


class PbmPerformanceClient:
    """Adapter for PBM P&L time-series queries.

    Interface contract stable; real HTTP implementation pending PBM endpoint
    delivery. Until then, callers use ``SynthPbmPerformanceClient`` which
    returns deterministic mock series.
    """

    def get_series(
        self,
        *,
        account_id: str,
        instance_id: str,
        view: str,
        window_start: datetime,
        window_end: datetime,
        per_venue: bool,
    ) -> _PerViewSeries | None:
        """Return a per-view series, or ``None`` if PBM has no data for this instance.

        ``None`` triggers graceful fallback in the route handler, whereas an
        exception is re-raised for the caller to classify.
        """
        raise NotImplementedError


class SynthPbmPerformanceClient(PbmPerformanceClient):
    """Default client — deterministic synthesis keyed on ``(instance_id, view)``.

    Used when ``CLOUD_MOCK_MODE=true`` or when the real PBM endpoint is
    unavailable. Returns the same shape as the real endpoint will.
    """

    def get_series(
        self,
        *,
        account_id: str,
        instance_id: str,
        view: str,
        window_start: datetime,
        window_end: datetime,
        per_venue: bool,
    ) -> _PerViewSeries | None:
        return _build_series(instance_id, view, window_start, window_end, per_venue=per_venue)


_default_client: PbmPerformanceClient = SynthPbmPerformanceClient()


def _get_pbm_client() -> PbmPerformanceClient:
    """FastAPI dependency — override in tests via ``dependency_overrides``."""
    return _default_client


def _account_for_view(view: str) -> str:
    """Map a view name to the odum representative-paper-account id.

    - ``backtest`` + ``paper`` → ``odum-paper`` (paper matching-engine fills)
    - ``live`` → ``odum-live`` (real venue fills when the instance has graduated)

    See ``memory/project_odum_paper_client_zero_representative_account_2026_04_21.md``
    for the client-zero rationale.
    """
    if view == "live":
        return "odum-live"
    return "odum-paper"


# ─── Entitlement gate (Plan C p1-pbm-wiring-followup) ────────────────────


def _check_performance_access(request: Request, instance_id: str) -> None:
    """Enforce the ``reporting``-OR-subscription gate on the /performance route.

    Rules (per module docstring §Permissioning):

    - Admin / internal-trader: bypass (``org_type=INTERNAL`` in context).
    - Any other tier-based or claims-based check: accept tiers
      ``enterprise | premium`` as a coarse surrogate for the ``reporting``
      entitlement until the fine-grained entitlement set is wired at the
      auth layer. Lower tiers (``basic``) are rejected with ``403``.
    - Subscription-based access (``org_id`` x ``instance_id``): deferred — the
      Firestore ``strategy_instance_subscriptions`` collection ships with
      Plan D Phase 2. Until then, the tier-based path is the only
      non-admin accept path.

    Raises ``HTTPException(403)`` when neither gate is satisfied.
    """
    ctx = get_entitlement_context(request)
    if ctx.is_internal:
        return
    # FOMO path: any tier ≥ premium has the reporting surface.
    reporting_tiers = {"enterprise", "premium", "reporting"}
    if ctx.tier in reporting_tiers:
        return
    # Subscription path: Plan D-delivered — placeholder hook. When the
    # subscription registry is wired, call it here.
    # if has_subscription(ctx.org_id, instance_id): return
    logger.info(
        "performance 403 org=%s tier=%s instance=%s (reporting+subscription unmet)",
        ctx.org_id,
        ctx.tier,
        instance_id,
    )
    raise HTTPException(
        status_code=403,
        detail=(
            "Performance series requires `reporting` entitlement or an active "
            "subscription on this instance."
        ),
    )


# ─── Deterministic synthesiser (used by SynthPbmPerformanceClient) ──────


def _instance_hash(instance_id: str) -> int:
    """Stable 32-bit integer from the instance_id, SHA256-based for uniformity."""
    digest = hashlib.sha256(instance_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _synthesise_series(
    instance_id: str,
    regime: str,
    start: datetime,
    end: datetime,
    *,
    slope_bps_per_day: float,
    vol_bps: float,
) -> list[_SeriesPoint]:
    """Deterministic daily series — smooth drift + instance-specific noise."""
    days = max(1, int((end - start).total_seconds() // 86400))
    h = _instance_hash(instance_id + regime)
    equity = 1_000_000.0
    points: list[_SeriesPoint] = []
    for i in range(days + 1):
        t = start + timedelta(days=i)
        # Deterministic pseudo-noise in [-1, 1] via sine of hashed phase.
        phase = ((h >> (i % 16)) & 0xFF) / 255.0
        noise = math.sin(phase * math.tau + i * 0.7) * (vol_bps / 10_000.0) * equity
        drift = (slope_bps_per_day / 10_000.0) * equity
        equity += drift + noise
        pnl = equity - 1_000_000.0
        points.append(
            _SeriesPoint(
                t=t.isoformat(),
                pnl=round(pnl, 2),
                equity=round(equity, 2),
            )
        )
    return points


def _venues_for_instance(instance_id: str) -> list[str]:
    """Deterministic venue list for per_venue expansion (mock)."""
    pool = ("OKX", "BINANCE", "BYBIT", "HYPERLIQUID", "GMX")
    h = _instance_hash(instance_id + "venues")
    count = 2 + (h % 3)
    offset = h % len(pool)
    return [pool[(offset + i) % len(pool)] for i in range(count)]


def _per_venue_slice(
    aggregate: list[_SeriesPoint],
    venues: Iterable[str],
    instance_id: str,
    regime: str,
) -> dict[str, list[_SeriesPoint]]:
    """Distribute aggregate P&L across venues with deterministic weights summing to 1."""
    venue_list = list(venues)
    weights: list[float] = []
    for v in venue_list:
        h = _instance_hash(f"{instance_id}:{regime}:{v}")
        weights.append(0.2 + (h % 1000) / 1000.0)
    total = sum(weights) or 1.0
    normalised = [w / total for w in weights]

    per_venue: dict[str, list[_SeriesPoint]] = {}
    for venue, weight in zip(venue_list, normalised, strict=True):
        per_venue[venue] = [
            _SeriesPoint(
                t=point.t,
                pnl=round(point.pnl * weight, 2),
                equity=round(1_000_000.0 + (point.equity - 1_000_000.0) * weight, 2),
            )
            for point in aggregate
        ]
    return per_venue


def _parse_rolling_or_iso(value: str, *, now: datetime) -> datetime:
    """Parse either a rolling window shorthand (``30d``) or ISO-8601."""
    v = value.strip().lower()
    if v == "now":
        return now
    if v.endswith("d") and v[:-1].isdigit():
        return now - timedelta(days=int(v[:-1]))
    if v.endswith("h") and v[:-1].isdigit():
        return now - timedelta(hours=int(v[:-1]))
    try:
        return datetime.fromisoformat(v.replace("z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid time value: {value}") from exc


def _parse_views(raw: str) -> _Views:
    parts = tuple(p.strip() for p in raw.split(",") if p.strip())
    if not parts:
        raise HTTPException(status_code=400, detail="views must be non-empty")
    unknown = [p for p in parts if p not in _VALID_VIEWS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown views: {','.join(unknown)} (allowed: backtest,paper,live)",
        )
    return parts


# ─── In-process cache (per-process; cheap mock surrogate for Redis) ─────


_CacheKey = tuple[str, str, str, str, bool]
_cache: dict[_CacheKey, tuple[float, _PerViewSeries]] = {}


def _cache_ttl(view: str) -> float:
    return _BACKTEST_TTL_S if view == "backtest" else _PAPER_LIVE_TTL_S


def _cached_series(
    key: _CacheKey,
    produce: callable[[], _PerViewSeries],  # type: ignore[name-defined]
) -> _PerViewSeries:
    view = key[1]
    now = time.monotonic()
    entry = _cache.get(key)
    if entry is not None:
        inserted_at, payload = entry
        if (now - inserted_at) < _cache_ttl(view):
            return payload
    fresh = produce()
    _cache[key] = (now, fresh)
    return fresh


def _build_series(
    instance_id: str,
    view: str,
    window_start: datetime,
    window_end: datetime,
    *,
    per_venue: bool,
) -> _PerViewSeries:
    if view == "backtest":
        aggregate = _synthesise_series(
            instance_id,
            "backtest",
            window_start,
            window_end,
            slope_bps_per_day=4.0,
            vol_bps=35.0,
        )
    elif view == "paper":
        aggregate = _synthesise_series(
            instance_id,
            "paper",
            window_start,
            window_end,
            slope_bps_per_day=3.0,
            vol_bps=45.0,
        )
    else:  # live
        aggregate = _synthesise_series(
            instance_id,
            "live",
            window_start,
            window_end,
            slope_bps_per_day=2.4,
            vol_bps=55.0,
        )

    venues_bucket: dict[str, list[_SeriesPoint]] | None = None
    if per_venue and view != "backtest":
        venues_bucket = _per_venue_slice(
            aggregate, _venues_for_instance(instance_id), instance_id, view
        )
    return _PerViewSeries(aggregate=aggregate, per_venue=venues_bucket)


def _resolve_transition_markers(
    start: datetime, end: datetime
) -> tuple[datetime | None, datetime | None]:
    """Return (paper_started_at, live_started_at) deterministic placeholders.

    Replaced by real ``StrategyInstanceLifecycle.phase_history`` lookups once
    Plan A Phase 3 surfaces those on the live service. Today: paper starts 55%
    through the window, live at 85%.
    """
    window = (end - start).total_seconds()
    if window <= 0:
        return None, None
    return (
        start + timedelta(seconds=window * 0.55),
        start + timedelta(seconds=window * 0.85),
    )


def _view_start_for(
    view: str,
    start: datetime,
    paper_started_at: datetime | None,
    live_started_at: datetime | None,
) -> datetime:
    """Pin the per-view window start to the view's maturity transition."""
    if view == "paper" and paper_started_at is not None:
        return paper_started_at
    if view == "live" and live_started_at is not None:
        return live_started_at
    return start


def _build_per_view_series(
    *,
    parsed_views: _Views,
    start: datetime,
    end: datetime,
    instance_id: str,
    per_venue: bool,
    paper_started_at: datetime | None,
    live_started_at: datetime | None,
    pbm_client: PbmPerformanceClient,
) -> dict[str, _PerViewSeries]:
    """Resolve each requested view to a cached per-view series (via PBM or synth)."""
    series: dict[str, _PerViewSeries] = {}
    for view in parsed_views:
        view_start = _view_start_for(view, start, paper_started_at, live_started_at)
        if view_start >= end:
            series[view] = _PerViewSeries(aggregate=[], per_venue=None)
            continue
        key: _CacheKey = (
            instance_id,
            view,
            view_start.isoformat(),
            end.isoformat(),
            per_venue,
        )

        def _produce(v: str = view, s: datetime = view_start) -> _PerViewSeries:
            account_id = _account_for_view(v)
            fetched = pbm_client.get_series(
                account_id=account_id,
                instance_id=instance_id,
                view=v,
                window_start=s,
                window_end=end,
                per_venue=per_venue,
            )
            if fetched is not None:
                return fetched
            return _build_series(instance_id, v, s, end, per_venue=per_venue)

        series[view] = _cached_series(key, _produce)
    return series


@router.get(
    "/strategy-instances/{instance_id}/performance",
    response_model=PerformanceSeriesResponse,
)
def get_strategy_instance_performance(
    request: Request,
    instance_id: str,
    views: str = Query(
        default="backtest,paper,live",
        description="Comma-separated subset of backtest,paper,live",
    ),
    from_: str = Query(
        default="180d",
        alias="from",
        description="Rolling window (e.g. 30d) or ISO-8601 UTC timestamp.",
    ),
    to: str = Query(
        default="now",
        description="Rolling window (e.g. now) or ISO-8601 UTC timestamp.",
    ),
    per_venue: bool = Query(default=False),
    pbm_client: PbmPerformanceClient = Depends(_get_pbm_client),
) -> PerformanceSeriesResponse:
    """Return the 3-regime P&L series for a strategy instance.

    See module docstring for source-of-truth + permissioning contract.
    """
    _check_performance_access(request, instance_id)
    parsed_views = _parse_views(views)
    now = datetime.now(UTC)
    start = _parse_rolling_or_iso(from_, now=now)
    end = _parse_rolling_or_iso(to, now=now)
    if start >= end:
        raise HTTPException(status_code=400, detail="from must precede to")

    paper_started_at, live_started_at = _resolve_transition_markers(start, end)
    series = _build_per_view_series(
        parsed_views=parsed_views,
        start=start,
        end=end,
        instance_id=instance_id,
        per_venue=per_venue,
        paper_started_at=paper_started_at,
        live_started_at=live_started_at,
        pbm_client=pbm_client,
    )

    phase_annotations: list[_PhaseAnnotation] = []
    if paper_started_at is not None:
        phase_annotations.append(
            _PhaseAnnotation(phase="paper_1d", at=paper_started_at.isoformat())
        )
    if live_started_at is not None:
        phase_annotations.append(
            _PhaseAnnotation(phase="live_early", at=live_started_at.isoformat())
        )

    logger.info(
        "GET /api/v1/strategy-instances/%s/performance views=%s per_venue=%s",
        instance_id,
        ",".join(parsed_views),
        per_venue,
    )
    return PerformanceSeriesResponse(
        instance_id=instance_id,
        series=series,
        transition_markers=_TransitionMarkers(
            paper_started_at=paper_started_at.isoformat() if paper_started_at else None,
            live_started_at=live_started_at.isoformat() if live_started_at else None,
        ),
        phase_annotations=phase_annotations,
    )


def reset_cache_for_tests() -> None:
    """Test hook — flush the in-process TTL cache."""
    _cache.clear()
