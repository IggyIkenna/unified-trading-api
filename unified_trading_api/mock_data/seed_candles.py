"""Brownian-motion OHLCV candle generator seeded from UAC representative sample."""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

from unified_api_contracts.registry.representative_sample import (
    CEFI_PERPETUAL_SPECS,
    CEFI_SPOT_SPECS,
    DEFI_INSTRUMENT_SPECS,
    SPORTS_INSTRUMENT_SPECS,
    TRADFI_EQUITY_SPECS,
    TRADFI_FUTURES_SPECS,
)

# ---------------------------------------------------------------------------
# Base prices (realistic as of March 2026)
# ---------------------------------------------------------------------------

_BASE_PRICES: dict[str, float] = {
    # CeFi spot/perp — keyed by base asset + quote where needed
    "BTC-USDT": 67000.0,
    "BTC-USD": 67000.0,
    "BTC-USDC": 67000.0,
    "BTC-KRW": 92_000_000.0,
    "ETH-USDT": 3500.0,
    "ETH-USD": 3500.0,
    "ETH": 3500.0,
    "SOL-USDT": 146.0,
    "SOL-USDT-SWAP": 146.0,
    "BTC": 67000.0,
    # TradFi equities
    "AAPL": 195.0,
    "QQQ": 490.0,
    "GLD": 215.0,
    "VIX": 15.0,
    # TradFi futures
    "ES": 5300.0,
    "ZB": 118.0,
    "ZN": 110.0,
    # DeFi — aTokens / debt tokens track ~1.0 (pegged to underlying)
    "aWETH": 3500.0,
    "aUSDC": 1.0,
    "aUSDT": 1.0,
    "variableDebtWETH": 3500.0,
    "variableDebtUSDC": 1.0,
    "variableDebtUSDT": 1.0,
    "cETHv3": 3500.0,
    "USDT-ETH-3000": 3500.0,
    "USDT-ETH": 3500.0,
    "stETH": 3500.0,
    "wstETH": 4050.0,
    "eETH": 3500.0,
    "weETH": 3700.0,
    "wstETH-USDC": 4050.0,
    "3pool": 1.0,
    "USDe": 1.0,
    "sUSDe": 1.05,
    "eUSDC": 1.0,
    # Sports — probability-based
    "NBA-DAL-MEM-SPREAD-5.5": 0.45,
    "NFL-ATL-CAR-SPREAD-3.5": 0.55,
    "EPL-MCI-ARS": 0.40,
    "NBA-LAL-BOS": 0.35,
}

# ---------------------------------------------------------------------------
# Volatility (daily %) per asset class
# ---------------------------------------------------------------------------

_DAILY_VOL: dict[str, float] = {
    "cefi_crypto": 0.025,
    "tradfi_equity": 0.007,
    "tradfi_etf": 0.005,
    "tradfi_index": 0.010,
    "tradfi_futures": 0.010,
    "defi_atoken": 0.008,
    "defi_pool": 0.015,
    "defi_lst": 0.010,
    "defi_yield": 0.005,
    "defi_debt": 0.008,
    "sports": 0.003,
}

# ---------------------------------------------------------------------------
# Interval definitions
# ---------------------------------------------------------------------------

_INTERVALS: list[tuple[str, int]] = [
    ("1m", 1),
    ("5m", 5),
    ("1h", 60),
    ("1d", 1440),
]

_N_CANDLES = 200
_ANCHOR = datetime(2026, 3, 22, 0, 0, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Market hours configuration per asset class
# ---------------------------------------------------------------------------
# Each entry: (open_hour_utc, open_minute_utc, close_hour_utc, close_minute_utc,
#              weekdays_only)
# None = 24/7 (no filtering)

_MARKET_HOURS: dict[str, tuple[int, int, int, int, bool] | None] = {
    # CeFi / DeFi / Sports: 24/7
    "cefi": None,
    "defi": None,
    "sports": None,
    # TradFi equities: NYSE 09:30-16:00 ET = 14:30-21:00 UTC
    "tradfi_equity": (14, 30, 21, 0, True),
    # TradFi futures: near-24hr 23:00-22:00 UTC, weekdays only
    "tradfi_futures": (23, 0, 22, 0, True),
}


def _is_within_market_hours(
    ts: datetime,
    market_class: str,
    interval_minutes: int,
) -> bool:
    """Return True if *ts* falls within market hours for the given class.

    Daily candles (interval_minutes >= 1440) only check for weekdays when
    the asset class requires it; intraday candles also check the time window.
    """
    hours = _MARKET_HOURS.get(market_class)
    if hours is None:
        return True

    open_h, open_m, close_h, close_m, weekdays_only = hours

    # Weekend filter (Mon=0 .. Sun=6)
    if weekdays_only and ts.weekday() >= 5:
        return False

    # Daily candles: all trading days pass (no intraday filter)
    if interval_minutes >= 1440:
        return True

    # Intraday: check time-of-day window
    ts_minutes = ts.hour * 60 + ts.minute
    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m

    if open_minutes < close_minutes:
        # Normal window (e.g. 14:30-21:00)
        return open_minutes <= ts_minutes < close_minutes
    # Overnight window (e.g. 23:00-22:00 = almost 24h, gap 22:00-23:00)
    return ts_minutes >= open_minutes or ts_minutes < close_minutes


# ---------------------------------------------------------------------------
# Brownian-motion OHLCV generator
# ---------------------------------------------------------------------------


def _generate_ohlcv(
    base_price: float,
    n_candles: int,
    daily_vol: float,
    interval_minutes: int,
    seed: int,
    market_class: str = "cefi",
) -> list[dict[str, object]]:
    """Generate *n_candles* synthetic OHLCV candles via geometric Brownian motion.

    For TradFi instruments, timestamps outside market hours are skipped.
    More candidate timestamps are generated to compensate, so the output
    always contains exactly *n_candles* candles.

    Returns newest-first (index 0 = most recent candle).
    """
    rng = random.Random(seed)

    # Scale daily vol to per-interval vol (sqrt-of-time)
    minutes_per_day = 1440.0
    interval_vol = daily_vol * math.sqrt(interval_minutes / minutes_per_day)

    candles: list[dict[str, object]] = []
    price = base_price

    # Generate enough candidates to fill n_candles after market-hours filtering.
    # Equity 1m has the worst ratio: ~390 valid mins per 10080-min week (~3.9%).
    # Use 8x for intraday tradfi, 3x for daily tradfi, 1x for 24/7 markets.
    has_filter = _MARKET_HOURS.get(market_class) is not None
    if not has_filter:
        max_candidates = n_candles
    elif interval_minutes >= 1440:
        max_candidates = n_candles * 3  # weekday filter only
    else:
        max_candidates = n_candles * 16  # intraday + weekday + weekend skip

    for i in range(max_candidates):
        ts = _ANCHOR - timedelta(minutes=interval_minutes * (max_candidates - i))

        if not _is_within_market_hours(ts, market_class, interval_minutes):
            # Advance price with a random walk even outside hours so that the
            # seed-deterministic price path stays consistent.
            rng.gauss(0.0, interval_vol / 2.0)
            continue

        open_price = price

        # Intra-candle ticks (4 sub-steps for realistic high/low)
        sub_prices = [open_price]
        p = open_price
        for _ in range(4):
            ret = rng.gauss(0.0, interval_vol / 2.0)
            p = p * math.exp(ret)
            sub_prices.append(p)

        close_price = sub_prices[-1]
        high_price = max(sub_prices)
        low_price = min(sub_prices)

        # Volume: base volume scaled by price with noise
        base_volume = 1000.0 * (100.0 / max(base_price, 0.01))
        volume = max(1.0, base_volume * (0.5 + rng.random()))

        candles.append(
            {
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": round(open_price, 8),
                "high": round(high_price, 8),
                "low": round(low_price, 8),
                "close": round(close_price, 8),
                "volume": round(volume, 2),
            }
        )

        price = close_price

        if len(candles) >= n_candles:
            break

    return candles


# ---------------------------------------------------------------------------
# Instrument → (base_price, daily_vol) mapping helpers
# ---------------------------------------------------------------------------


def _vol_for_defi_type(defi_type: str) -> float:
    """Return daily vol for a DeFi instrument type."""
    mapping: dict[str, str] = {
        "A_TOKEN": "defi_atoken",
        "DEBT_TOKEN": "defi_debt",
        "POOL": "defi_pool",
        "LST": "defi_lst",
        "YIELD_BEARING": "defi_yield",
    }
    return _DAILY_VOL[mapping.get(defi_type, "defi_pool")]


def _build_instrument_configs() -> list[tuple[str, float, float, str]]:
    """Build (instrument_id, base_price, daily_vol, market_class) tuples from UAC specs."""
    configs: list[tuple[str, float, float, str]] = []

    # CeFi Spot
    for spec in CEFI_SPOT_SPECS:
        symbol = spec["symbol"]
        inst_id = f"{spec['venue']}:{symbol}"
        price = _BASE_PRICES.get(str(symbol), 100.0)
        configs.append((inst_id, price, _DAILY_VOL["cefi_crypto"], "cefi"))

    # CeFi Perpetuals
    for spec in CEFI_PERPETUAL_SPECS:
        symbol = str(spec["symbol"])
        inst_id = f"{spec['venue']}:{symbol}"
        price = _BASE_PRICES.get(symbol, 100.0)
        configs.append((inst_id, price, _DAILY_VOL["cefi_crypto"], "cefi"))

    # TradFi Equities
    for spec in TRADFI_EQUITY_SPECS:
        symbol = spec["symbol"]
        inst_id = f"{spec['venue']}:{symbol}"
        price = _BASE_PRICES.get(str(symbol), 100.0)
        asset_class = spec.get("asset_class", "tradfi_equity")
        vol = _DAILY_VOL.get(str(asset_class), _DAILY_VOL["tradfi_equity"])
        configs.append((inst_id, price, vol, "tradfi_equity"))

    # TradFi Futures
    for spec in TRADFI_FUTURES_SPECS:
        root = str(spec["root"])
        inst_id = f"{spec['venue']}:{root}"
        price = _BASE_PRICES.get(root, 100.0)
        configs.append((inst_id, price, _DAILY_VOL["tradfi_futures"], "tradfi_futures"))

    # DeFi
    for spec in DEFI_INSTRUMENT_SPECS:
        symbol = str(spec["symbol"])
        inst_id = f"{spec['venue']}:{symbol}"
        price = _BASE_PRICES.get(symbol, 1.0)
        defi_type = str(spec.get("type", "POOL"))
        vol = _vol_for_defi_type(defi_type)
        configs.append((inst_id, price, vol, "defi"))

    # Sports
    for spec in SPORTS_INSTRUMENT_SPECS:
        symbol = spec["symbol"]
        inst_id = f"{spec['venue']}:{symbol}"
        price = _BASE_PRICES.get(str(symbol), 0.50)
        configs.append((inst_id, price, _DAILY_VOL["sports"], "sports"))

    return configs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_candles() -> dict[str, list[dict[str, object]]]:
    """Generate deterministic OHLCV candles for all representative instruments.

    Returns a dict with keys ``candles_1m``, ``candles_5m``, ``candles_1h``,
    ``candles_1d``. Each value is a flat list of candle dicts (all instruments
    concatenated), with an ``instrument`` field added to each candle.
    """
    instrument_configs = _build_instrument_configs()

    result: dict[str, list[dict[str, object]]] = {f"candles_{label}": [] for label, _ in _INTERVALS}

    for inst_idx, (inst_id, base_price, daily_vol, market_class) in enumerate(
        instrument_configs,
    ):
        for interval_idx, (label, minutes) in enumerate(_INTERVALS):
            seed = inst_idx * 100 + interval_idx
            candles = _generate_ohlcv(
                base_price,
                _N_CANDLES,
                daily_vol,
                minutes,
                seed,
                market_class,
            )

            for candle in candles:
                candle["instrument"] = inst_id

            result[f"candles_{label}"].extend(candles)

    return result
