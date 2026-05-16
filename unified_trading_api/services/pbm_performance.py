"""Plan C — HTTP-backed PBM performance client (real PBM endpoint).

Couples to the position-balance-monitor-service ``pnl-series`` endpoint
shipped at ``/api/v1/accounts/{account_id}/pnl-series``.

Selection between the synthesised and real client happens in the route
handler (``routes/strategy_performance.py`` — ``_get_pbm_client``); this
file contains only the HTTP adapter. Imports the abstract ``PbmPerformanceClient``
+ DTO ``_PerViewSeries`` from the route module to avoid circular imports while
the contract surface remains co-located with the consumer.

Failure mode (per Plan C contract):
  * Network / 5xx / timeout → returns ``None`` so the route falls back to
    ``SynthPbmPerformanceClient``. NEVER raises out of the adapter.
  * 404 → returns ``None`` (instance not yet onboarded to odum-paper).
  * 200 with empty series → returns ``None`` so the overlay still falls back.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

import httpx

from unified_trading_api.routes.strategy_performance import (  # noqa: qg-deep-import — self-package
    PbmPerformanceClient,
    SynthPbmPerformanceClient,
    _account_for_view,  # pyright: ignore[reportPrivateUsage]  # SAME-PACKAGE — co-located helper.
    _PerViewSeries,  # pyright: ignore[reportPrivateUsage]  # SAME-PACKAGE — co-located DTO until extraction completes (see route docstring §UTA-side ``HttpPbmPerformanceClient`` placement).
    _SeriesPoint,  # pyright: ignore[reportPrivateUsage]  # SAME-PACKAGE — co-located DTO.
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0


class HttpPbmPerformanceClient(PbmPerformanceClient):
    """Real PBM-backed implementation.

    Construction::

        client = HttpPbmPerformanceClient(
            base_url="http://position-balance-monitor:8080",
        )
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = http_client or httpx.Client(timeout=timeout_seconds)

    def _fetch_series_payload(
        self,
        url: str,
        params: dict[str, str],
        *,
        log_context: tuple[str, str, str],
    ) -> dict[str, Any] | None:
        """Fetch + JSON-decode the pnl-series payload. None on any non-2xx or transport error."""
        account, instance, view = log_context
        try:
            response = self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.warning(
                "PBM pnl-series fetch failed account=%s instance=%s view=%s: %s",
                account,
                instance,
                view,
                exc,
            )
            return None
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            logger.warning(
                "PBM pnl-series HTTP %s account=%s instance=%s view=%s",
                response.status_code,
                account,
                instance,
                view,
            )
            return None
        try:
            return cast(dict[str, Any], response.json())
        except ValueError as exc:
            logger.warning("PBM pnl-series JSON decode failed: %s", exc)
            return None

    @staticmethod
    def _series_list_from_payload(payload: dict[str, Any]) -> list[object] | None:
        """Return the series list from a payload, or None if empty/malformed."""
        series_obj: object = payload.get("series") or []
        if not isinstance(series_obj, list):
            return None
        series_list: list[object] = cast(list[object], series_obj)
        return series_list or None

    @staticmethod
    def _build_buckets(
        series_list: list[object], per_venue: bool
    ) -> tuple[list[_SeriesPoint], dict[str, list[_SeriesPoint]]]:
        """Project the raw series list into an aggregate + optional per-venue buckets."""
        aggregate: list[_SeriesPoint] = []
        per_venue_buckets: dict[str, list[_SeriesPoint]] = {}
        for entry in series_list:
            if not isinstance(entry, dict):
                continue
            entry_dict = cast(dict[str, Any], entry)
            ts: object = entry_dict.get("timestamp")
            pnl: object = entry_dict.get("pnl")
            venue_raw: object = entry_dict.get("venue")
            if not isinstance(ts, str) or not isinstance(pnl, (int, float)):
                continue
            running = float(pnl)
            point = _SeriesPoint(t=ts, pnl=running, equity=running)
            aggregate.append(point)
            if per_venue and isinstance(venue_raw, str):
                per_venue_buckets.setdefault(venue_raw, []).append(point)
        return aggregate, per_venue_buckets

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
        # Use the canonical odum-paper / odum-live account mapping so callers
        # need not pre-resolve.
        resolved_account = account_id or _account_for_view(view)
        url = f"{self._base_url}/api/v1/accounts/{resolved_account}/pnl-series"
        params = {
            "instance_id": instance_id,
            "from": window_start.date().isoformat(),
            "to": window_end.date().isoformat(),
            "per_venue": "true" if per_venue else "false",
        }
        payload = self._fetch_series_payload(
            url, params, log_context=(resolved_account, instance_id, view)
        )
        if payload is None:
            return None
        series_list = self._series_list_from_payload(payload)
        if series_list is None:
            return None
        aggregate, per_venue_buckets = self._build_buckets(series_list, per_venue)
        if not aggregate:
            return None
        return _PerViewSeries(
            aggregate=aggregate,
            per_venue=per_venue_buckets if per_venue and per_venue_buckets else None,
        )


def make_pbm_performance_client(
    *,
    base_url: str | None,
    fall_back_to_synth: bool = True,
) -> PbmPerformanceClient:
    """Factory used by the route handler at startup.

    Returns the HTTP client when ``base_url`` is provided, otherwise the
    synthesised client. When ``fall_back_to_synth`` is True (default) and
    construction of the HTTP client raises, the synth client is returned —
    the route never crashes due to PBM wire-up failure.
    """
    if not base_url:
        return SynthPbmPerformanceClient()
    try:
        return HttpPbmPerformanceClient(base_url=base_url)
    except Exception as exc:
        if fall_back_to_synth:
            logger.warning("HttpPbmPerformanceClient init failed: %s; using synth", exc)
            return SynthPbmPerformanceClient()
        raise
