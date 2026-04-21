"""Ticker price generation for all instruments in the UAC representative sample.

ARCHITECTURAL CONSTRAINT:
- DO NOT hardcode instrument lists. Import from UAC representative_sample.py.
- Tickers serve as starting point for WebSocket mock tick generator (Agent 5).
- Both _live and _batch variants generated (batch = yesterday's close).

Generates deterministic ticker records (price, bid, ask, volume, change)
for every instrument registered in representative_sample.py. Two modes:

- ``generate_tickers_live()``  — current (real-time) prices
- ``generate_tickers_batch()`` — yesterday's close (~0.5-2% offset)
"""

from __future__ import annotations

from unified_api_contracts.registry.representative_sample import (  # noqa: qg-deep-import — UAC internal facade
    CEFI_PERPETUAL_SPECS,
    CEFI_SPOT_SPECS,
    DEFI_INSTRUMENT_SPECS,
    SPORTS_INSTRUMENT_SPECS,
    TRADFI_EQUITY_SPECS,
    TRADFI_FUTURES_SPECS,
)

# ---------------------------------------------------------------------------
# Base prices (March 2026 estimates) keyed by base asset or symbol
# ---------------------------------------------------------------------------

BASE_PRICES: dict[str, float] = {
    # CeFi base assets
    "BTC": 67_000.0,
    "ETH": 3_500.0,
    "SOL": 146.0,
    # KRW-quoted BTC (Upbit)
    "BTC-KRW": 92_000_000.0,
    # TradFi equities / indices
    "AAPL": 195.0,
    "QQQ": 490.0,
    "GLD": 215.0,
    "VIX": 15.0,
    # TradFi futures
    "ES": 5_300.0,
    "ZB": 118.0,
    "ZN": 110.0,
    # DeFi aTokens (interest-accruing, slightly above 1.0)
    "aWETH": 1.04,
    "aUSDC": 1.02,
    "aUSDT": 1.01,
    # DeFi debt tokens (track underlying 1:1)
    "variableDebtWETH": 1.0,
    "variableDebtUSDC": 1.0,
    "variableDebtUSDT": 1.0,
    # Compound V3
    "cETHv3": 1.03,
    # Uniswap / DEX pool tokens
    "USDT-ETH-3000": 3_500.0,
    "USDT-ETH": 3_500.0,
    # Curve 3pool (stablecoin LP ~1.0)
    "3pool": 1.02,
    # Lido
    "stETH": 3_510.0,
    "wstETH": 4_050.0,
    # EtherFi
    "eETH": 3_505.0,
    "weETH": 3_700.0,
    # Morpho
    "wstETH-USDC": 4_050.0,
    # Ethena
    "USDe": 1.00,
    "sUSDe": 1.05,
    # Euler
    "eUSDC": 1.02,
}

# CeFi perpetual price offsets from spot (basis)
_PERP_OFFSETS: dict[str, float] = {
    "BTC-USDT": 67_010.0,
    "BTC-USDC": 67_020.0,
    "ETH": 3_502.0,
    "SOL-USDT-SWAP": 146.10,
    "BTC": 67_015.0,
}

# Volume ranges by asset class (24h notional, deterministic)
_VOLUME_MAP: dict[str, float] = {
    "cefi_spot": 1_250_000_000.0,
    "cefi_perp": 2_800_000_000.0,
    "tradfi_equity": 85_000_000.0,
    "tradfi_futures": 120_000_000.0,
    "defi": 45_000_000.0,
    "sports": 2_500_000.0,
}

# Deterministic 24h change percentages per symbol (keeps output stable)
_CHANGE_PCT: dict[str, float] = {
    "BTC": 1.23,
    "ETH": -0.87,
    "SOL": 2.45,
    "AAPL": 0.34,
    "QQQ": -0.12,
    "GLD": 0.56,
    "VIX": -3.20,
    "ES": 0.18,
    "ZB": -0.05,
    "ZN": -0.08,
}

# Frozen timestamp for deterministic output
_LIVE_TS = "2026-03-22T12:00:00Z"
_BATCH_TS = "2026-03-21T21:00:00Z"


# ---------------------------------------------------------------------------
# Spread helpers
# ---------------------------------------------------------------------------


def _apply_spread(price: float, spread_pct: float) -> tuple[float, float]:
    """Return (bid, ask) symmetrically around *price*."""
    half = price * spread_pct / 2.0
    return round(price - half, 8), round(price + half, 8)


def _get_change_pct(key: str) -> float:
    """Deterministic change % — fall back to a stable hash-derived value."""
    if key in _CHANGE_PCT:
        return _CHANGE_PCT[key]
    # Stable fallback: sum of char ordinals mod 400, shifted to [-2, +2]
    raw = sum(ord(c) for c in key) % 400
    return round((raw - 200) / 100.0, 2)


# ---------------------------------------------------------------------------
# Per-asset-class generators
# ---------------------------------------------------------------------------


def _cefi_spot_tickers(timestamp: str) -> list[dict[str, object]]:
    tickers: list[dict[str, object]] = []
    for spec in CEFI_SPOT_SPECS:
        symbol = str(spec["symbol"])
        base = str(spec["base"])
        venue = str(spec["venue"])

        # KRW-quoted pairs use a dedicated price
        price_key = symbol if symbol in BASE_PRICES else base
        price = BASE_PRICES.get(price_key, 100.0)

        bid, ask = _apply_spread(price, 0.0001)  # 0.01%
        change = _get_change_pct(base)

        tickers.append(
            {
                "instrument": symbol,
                "venue": venue,
                "price": price,
                "bid": bid,
                "ask": ask,
                "volume_24h": _VOLUME_MAP["cefi_spot"],
                "change_24h_pct": change,
                "asset_class": "cefi_spot",
                "timestamp": timestamp,
            }
        )
    return tickers


def _cefi_perp_tickers(timestamp: str) -> list[dict[str, object]]:
    tickers: list[dict[str, object]] = []
    for spec in CEFI_PERPETUAL_SPECS:
        symbol = str(spec["symbol"])
        venue = str(spec["venue"])
        base = str(spec["base"])

        price = _PERP_OFFSETS.get(symbol, BASE_PRICES.get(base, 100.0))

        bid, ask = _apply_spread(price, 0.0001)  # 0.01%
        change = _get_change_pct(base)

        tickers.append(
            {
                "instrument": symbol,
                "venue": venue,
                "price": price,
                "bid": bid,
                "ask": ask,
                "volume_24h": _VOLUME_MAP["cefi_perp"],
                "change_24h_pct": change,
                "asset_class": "cefi_perpetual",
                "timestamp": timestamp,
            }
        )
    return tickers


def _tradfi_equity_tickers(timestamp: str) -> list[dict[str, object]]:
    tickers: list[dict[str, object]] = []
    for spec in TRADFI_EQUITY_SPECS:
        symbol = str(spec["symbol"])
        venue = str(spec["venue"])
        asset_class = str(spec.get("asset_class", "tradfi_equity"))

        price = BASE_PRICES.get(symbol, 100.0)
        bid, ask = _apply_spread(price, 0.00005)  # 0.005%
        change = _get_change_pct(symbol)

        tickers.append(
            {
                "instrument": symbol,
                "venue": venue,
                "price": price,
                "bid": bid,
                "ask": ask,
                "volume_24h": _VOLUME_MAP["tradfi_equity"],
                "change_24h_pct": change,
                "asset_class": asset_class,
                "timestamp": timestamp,
            }
        )
    return tickers


def _tradfi_futures_tickers(timestamp: str) -> list[dict[str, object]]:
    tickers: list[dict[str, object]] = []
    for spec in TRADFI_FUTURES_SPECS:
        root = str(spec["root"])
        venue = str(spec["venue"])

        price = BASE_PRICES.get(root, 100.0)
        bid, ask = _apply_spread(price, 0.00005)  # 0.005%
        change = _get_change_pct(root)

        tickers.append(
            {
                "instrument": root,
                "venue": venue,
                "price": price,
                "bid": bid,
                "ask": ask,
                "volume_24h": _VOLUME_MAP["tradfi_futures"],
                "change_24h_pct": change,
                "asset_class": "tradfi_futures",
                "timestamp": timestamp,
            }
        )
    return tickers


def _defi_tickers(timestamp: str) -> list[dict[str, object]]:
    tickers: list[dict[str, object]] = []
    for spec in DEFI_INSTRUMENT_SPECS:
        symbol = str(spec["symbol"])
        venue = str(spec["venue"])
        inst_type = str(spec.get("type", "POOL"))

        price = BASE_PRICES.get(symbol, 1.0)

        # DeFi spread: 0.1% for lending/yield, 0.3% for pools
        spread = 0.003 if inst_type == "POOL" else 0.001
        bid, ask = _apply_spread(price, spread)
        change = _get_change_pct(symbol)

        tickers.append(
            {
                "instrument": symbol,
                "venue": venue,
                "price": price,
                "bid": bid,
                "ask": ask,
                "volume_24h": _VOLUME_MAP["defi"],
                "change_24h_pct": change,
                "asset_class": "defi",
                "timestamp": timestamp,
            }
        )
    return tickers


def _sports_tickers(timestamp: str) -> list[dict[str, object]]:
    """Sports instruments use probability-style prices (0.30-0.70)."""
    # Deterministic probabilities per symbol
    _probs: dict[str, float] = {
        "NBA-DAL-MEM-SPREAD-5.5": 0.45,
        "NFL-ATL-CAR-SPREAD-3.5": 0.52,
        "EPL-MCI-ARS": 0.38,
        "NBA-LAL-BOS": 0.61,
    }

    tickers: list[dict[str, object]] = []
    for spec in SPORTS_INSTRUMENT_SPECS:
        symbol = str(spec["symbol"])
        venue = str(spec["venue"])
        asset_class = str(spec.get("asset_class", "sports"))

        price = _probs.get(symbol, 0.50)
        # Sports spread: 2-5% (use 3% as default)
        spread = 0.03
        bid, ask = _apply_spread(price, spread)
        change = _get_change_pct(symbol)

        tickers.append(
            {
                "instrument": symbol,
                "venue": venue,
                "price": price,
                "bid": bid,
                "ask": ask,
                "volume_24h": _VOLUME_MAP["sports"],
                "change_24h_pct": change,
                "asset_class": asset_class,
                "timestamp": timestamp,
            }
        )
    return tickers


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_tickers_live() -> list[dict[str, object]]:
    """Generate current ticker prices for all representative instruments."""
    ts = _LIVE_TS
    tickers: list[dict[str, object]] = []
    tickers.extend(_cefi_spot_tickers(ts))
    tickers.extend(_cefi_perp_tickers(ts))
    tickers.extend(_tradfi_equity_tickers(ts))
    tickers.extend(_tradfi_futures_tickers(ts))
    tickers.extend(_defi_tickers(ts))
    tickers.extend(_sports_tickers(ts))
    return tickers


def generate_tickers_batch() -> list[dict[str, object]]:
    """Generate yesterday's close prices (~0.5-2% offset from live)."""
    ts = _BATCH_TS

    # Start with live prices, then apply a deterministic offset
    live = generate_tickers_live()
    batch: list[dict[str, object]] = []

    for ticker in live:
        instrument = str(ticker["instrument"])
        price = float(str(ticker["price"]))

        # Deterministic offset: hash-derived, between -2% and +0.5%
        raw = sum(ord(c) for c in instrument) % 250
        offset_pct = (raw - 200) / 10_000.0  # range: -0.02 to +0.005

        batch_price = round(price * (1.0 + offset_pct), 8)

        # Recalculate bid/ask with same spread logic
        asset_class = str(ticker["asset_class"])
        if asset_class == "defi":
            spread = 0.003
        elif asset_class in ("prediction", "sports"):
            spread = 0.03
        elif asset_class.startswith("tradfi"):
            spread = 0.00005
        else:
            spread = 0.0001

        bid, ask = _apply_spread(batch_price, spread)

        batch.append(
            {
                "instrument": instrument,
                "venue": str(ticker["venue"]),
                "price": batch_price,
                "bid": bid,
                "ask": ask,
                "volume_24h": ticker["volume_24h"],
                "change_24h_pct": ticker["change_24h_pct"],
                "asset_class": asset_class,
                "timestamp": ts,
            }
        )

    return batch
