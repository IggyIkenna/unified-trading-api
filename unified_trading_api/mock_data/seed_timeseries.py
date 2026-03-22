from __future__ import annotations

import math
import random
from datetime import date, timedelta

_BASE_DATE = date(2026, 3, 22)
_HISTORY = 180
_BASE_NAV = 1_000_000.0

# ── archetype inference from strategy name tokens ──
_ARCHETYPE_KEYWORDS: dict[str, str] = {
    "MOM": "momentum",
    "TREND": "momentum",
    "STAT_ARB": "mean-reversion",
    "REBAL": "mean-reversion",
    "VOL_SURF": "mean-reversion",
    "MM": "market-making",
    "GRID": "market-making",
    "YIELD": "defi-yield",
    "FLASH_LOAN": "defi-yield",
    "LP": "defi-yield",
    "LENDING": "defi-yield",
    "BASIS": "basis-trade",
    "FUNDING_ARB": "basis-trade",
    "SPORTS": "sports",
    "PREDICTION": "sports",
    "ML_DIR": "ml-directional",
    "SENT": "ml-directional",
    "ARB": "arbitrage",
    "PERP": "momentum",
}

# daily_mu, daily_sigma, max_drawdown_frac, win_bias (0-1, >0.5 = profitable)
_ARCHETYPE_PARAMS: dict[str, tuple[float, float, float, float]] = {
    "momentum": (0.0008, 0.012, 0.18, 0.62),
    "mean-reversion": (0.0003, 0.005, 0.08, 0.58),
    "market-making": (0.0003, 0.002, 0.04, 0.70),
    "defi-yield": (0.0005, 0.006, 0.12, 0.60),
    "basis-trade": (0.0004, 0.003, 0.06, 0.65),
    "sports": (0.0000, 0.015, 0.15, 0.52),
    "ml-directional": (0.0006, 0.010, 0.16, 0.58),
    "arbitrage": (0.0002, 0.001, 0.03, 0.72),
}


def _infer_archetype(name: str) -> str:
    upper = name.upper()
    # check multi-word keys first (longest match)
    for kw in sorted(_ARCHETYPE_KEYWORDS, key=len, reverse=True):
        if kw in upper:
            return _ARCHETYPE_KEYWORDS[kw]
    return "momentum"


def _generate_curve(
    strategy_id: str,
    archetype: str,
    num_days: int,
) -> list[dict[str, object]]:
    rng = random.Random(hash(strategy_id))  # nosec B311
    mu, sigma, max_dd, win_bias = _ARCHETYPE_PARAMS.get(archetype, _ARCHETYPE_PARAMS["momentum"])

    # ~40% of strategies are unprofitable — flip sign based on seed
    if rng.random() > win_bias:
        mu = -abs(mu) * 1.5

    nav = _BASE_NAV
    hwm = nav
    cum_pnl = 0.0
    start = _BASE_DATE - timedelta(days=num_days - 1)
    points: list[dict[str, object]] = []

    for i in range(num_days):
        day = start + timedelta(days=i)

        if archetype == "sports":
            # step-function: ~30% of days have events
            daily = nav * rng.gauss(mu, sigma) if rng.random() < 0.30 else 0.0
        elif archetype == "market-making":
            # steady income with rare spikes
            daily = nav * abs(rng.gauss(mu, sigma * 0.3))
            if rng.random() < 0.03:
                daily = -nav * rng.uniform(0.005, 0.015)
        else:
            # regime shifts via sine modulation
            regime = 1.0 + 0.4 * math.sin(2 * math.pi * i / 90)
            daily = nav * rng.gauss(mu * regime, sigma)

        cum_pnl += daily
        nav += daily
        hwm = max(hwm, nav)
        dd = (hwm - nav) / hwm if hwm > 0 else 0.0
        # clamp drawdown to archetype max
        if dd > max_dd:
            nav = hwm * (1.0 - max_dd)
            cum_pnl = nav - _BASE_NAV
            dd = max_dd

        points.append(
            {
                "strategy_id": strategy_id,
                "date": day.isoformat(),
                "daily_pnl": round(daily, 2),
                "cumulative_pnl": round(cum_pnl, 2),
                "drawdown": round(dd, 6),
                "nav": round(nav, 2),
            }
        )

    return points


def _period_pnl(points: list[dict[str, object]], start: date) -> float:
    return sum(float(str(p["daily_pnl"])) for p in points if str(p["date"]) >= start.isoformat())


def generate_pnl_timeseries(
    strategies: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Generate 180-day PnL time-series for each strategy."""
    today = _BASE_DATE
    ytd_start = date(today.year, 1, 1)
    qtd_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
    mtd_start = date(today.year, today.month, 1)

    all_records: list[dict[str, object]] = []

    for strat in strategies:
        sid = str(strat.get("id", strat.get("strategy_id", "")))  # noqa: qg-empty-fallback
        name = str(strat.get("name", ""))  # noqa: qg-empty-fallback
        archetype = str(strat.get("archetype", "")) or _infer_archetype(name)  # noqa: qg-empty-fallback

        inception_raw = strat.get("inception_date")
        if isinstance(inception_raw, str) and inception_raw:
            inc = date.fromisoformat(inception_raw)
            num_days = min((today - inc).days + 1, _HISTORY)
        else:
            num_days = _HISTORY

        points = _generate_curve(sid, archetype, max(num_days, 1))

        # attach period summaries to each point
        ytd = round(_period_pnl(points, ytd_start), 2)
        mtd = round(_period_pnl(points, mtd_start), 2)
        qtd = round(_period_pnl(points, qtd_start), 2)
        for p in points:
            p["ytd_pnl"] = ytd
            p["mtd_pnl"] = mtd
            p["qtd_pnl"] = qtd

        all_records.extend(points)

    return all_records
