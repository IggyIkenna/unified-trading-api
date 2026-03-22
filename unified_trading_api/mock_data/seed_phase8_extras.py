"""Phase 8 extra seed generators — news, regime, portfolio greeks, risk exposure.

Extracted from seed_phase8.py to keep file sizes under 900 lines.
"""

from __future__ import annotations

from typing import Final

# ── Org constants (mirror seed_phase8.py) ─────────────────────────────
_O: Final[str] = "odum-internal"
_A: Final[str] = "acme"
_V: Final[str] = "vertex"
_B: Final[str] = "beta"

# ── Reference date ────────────────────────────────────────────────────
_BASE_DATE: Final[str] = "2026-03-22"
_BASE_TS: Final[str] = "2026-03-22T00:00:00Z"


def gen_news() -> list[dict[str, object]]:
    """Recent news items (last 48 hours from base date)."""
    items: list[dict[str, object]] = [
        # Market moves
        {
            "id": "news-001",
            "title": "Bitcoin breaks $67,000 as institutional inflows accelerate",
            "source": "CoinDesk",
            "timestamp": "2026-03-22T06:30:00Z",
            "category": "market_move",
            "relevance_score": 0.95,
            "linked_instruments": ["BTC-USDT", "BTC-USD"],
        },
        {
            "id": "news-002",
            "title": "Ethereum gas fees hit 6-month low after Dencun upgrade effects",
            "source": "The Block",
            "timestamp": "2026-03-22T04:15:00Z",
            "category": "crypto",
            "relevance_score": 0.88,
            "linked_instruments": ["ETH-USDT", "ETH-USD"],
        },
        {
            "id": "news-003",
            "title": "S&P 500 edges higher on strong jobs data",
            "source": "Reuters",
            "timestamp": "2026-03-21T21:00:00Z",
            "category": "macro",
            "relevance_score": 0.72,
            "linked_instruments": ["SPY", "ES-PERP"],
        },
        # Regulatory
        {
            "id": "news-004",
            "title": "EU finalises MiCA implementation rules for crypto exchanges",
            "source": "Financial Times",
            "timestamp": "2026-03-22T08:00:00Z",
            "category": "regulatory",
            "relevance_score": 0.90,
            "linked_instruments": ["BTC-USDT", "ETH-USDT"],
        },
        {
            "id": "news-005",
            "title": "SEC approves spot Solana ETF application from BlackRock",
            "source": "Bloomberg",
            "timestamp": "2026-03-21T16:30:00Z",
            "category": "regulatory",
            "relevance_score": 0.93,
            "linked_instruments": ["SOL-USDT", "SOL-USD"],
        },
        {
            "id": "news-006",
            "title": "FCA tightens reporting deadlines for crypto derivatives",
            "source": "Risk.net",
            "timestamp": "2026-03-21T14:00:00Z",
            "category": "regulatory",
            "relevance_score": 0.78,
            "linked_instruments": [],
        },
        # Macro
        {
            "id": "news-007",
            "title": "Fed holds rates steady, signals potential June cut",
            "source": "CNBC",
            "timestamp": "2026-03-21T18:00:00Z",
            "category": "macro",
            "relevance_score": 0.96,
            "linked_instruments": ["SPY", "ES-PERP", "NQ-PERP"],
        },
        {
            "id": "news-008",
            "title": "US 10Y Treasury yield falls to 4.1% on dovish Fed language",
            "source": "Bloomberg",
            "timestamp": "2026-03-21T19:30:00Z",
            "category": "macro",
            "relevance_score": 0.82,
            "linked_instruments": ["TLT", "ZN-FUT"],
        },
        {
            "id": "news-009",
            "title": "ECB warns of renewed inflation risks in Q2",
            "source": "Reuters",
            "timestamp": "2026-03-21T12:00:00Z",
            "category": "macro",
            "relevance_score": 0.70,
            "linked_instruments": ["EUR/USD"],
        },
        # Crypto-specific
        {
            "id": "news-010",
            "title": "Aave V3 TVL surpasses $25B as DeFi lending demand surges",
            "source": "DeFi Llama",
            "timestamp": "2026-03-22T02:45:00Z",
            "category": "crypto",
            "relevance_score": 0.85,
            "linked_instruments": ["AAVE-USDT", "ETH-USDT"],
        },
        {
            "id": "news-011",
            "title": "Binance reports record Q1 derivatives volume",
            "source": "The Block",
            "timestamp": "2026-03-21T10:00:00Z",
            "category": "crypto",
            "relevance_score": 0.75,
            "linked_instruments": ["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        },
        {
            "id": "news-012",
            "title": "Hyperliquid open interest reaches $4.2B all-time high",
            "source": "CoinGecko",
            "timestamp": "2026-03-22T01:00:00Z",
            "category": "crypto",
            "relevance_score": 0.80,
            "linked_instruments": ["BTC-USDT", "ETH-USDT"],
        },
        {
            "id": "news-013",
            "title": "Uniswap V4 hooks drive 40% increase in LP participation",
            "source": "Messari",
            "timestamp": "2026-03-21T09:00:00Z",
            "category": "crypto",
            "relevance_score": 0.77,
            "linked_instruments": ["UNI-USDT", "ETH-USDT"],
        },
        # Market move
        {
            "id": "news-014",
            "title": "Crude oil falls 3% on OPEC+ output increase announcement",
            "source": "Reuters",
            "timestamp": "2026-03-21T15:45:00Z",
            "category": "market_move",
            "relevance_score": 0.68,
            "linked_instruments": ["CL-FUT"],
        },
        {
            "id": "news-015",
            "title": "Gold hits record $2,350 amid geopolitical uncertainty",
            "source": "Bloomberg",
            "timestamp": "2026-03-22T07:00:00Z",
            "category": "market_move",
            "relevance_score": 0.74,
            "linked_instruments": ["GC-FUT", "GLD"],
        },
        {
            "id": "news-016",
            "title": "Korean Won weakens past 1,330 on BOK rate hold",
            "source": "Nikkei Asia",
            "timestamp": "2026-03-21T08:30:00Z",
            "category": "macro",
            "relevance_score": 0.62,
            "linked_instruments": ["KRW/USD"],
        },
        {
            "id": "news-017",
            "title": "Flash crash in DOGE-USDT triggers cascading liquidations",
            "source": "CoinTelegraph",
            "timestamp": "2026-03-22T03:20:00Z",
            "category": "market_move",
            "relevance_score": 0.83,
            "linked_instruments": ["DOGE-USDT"],
        },
        {
            "id": "news-018",
            "title": "Premier League clubs push for expanded crypto sponsorship rules",
            "source": "Sky Sports",
            "timestamp": "2026-03-21T11:00:00Z",
            "category": "regulatory",
            "relevance_score": 0.55,
            "linked_instruments": [],
        },
    ]
    return items


def gen_market_regime() -> list[dict[str, object]]:
    """Current market regime snapshot."""
    return [
        {
            "regime_id": "regime-current",
            "regime": "risk_on",
            "multiplier": 1.0,
            "signals": {
                "btc_trend": "bullish",
                "eth_trend": "bullish",
                "vol_regime": "low",
                "funding_rate_bias": "positive",
                "defi_tvl_trend": "expanding",
                "correlation_regime": "moderate",
                "liquidity_score": 0.82,
                "fear_greed_index": 68,
            },
            "previous_regime": "neutral",
            "regime_since": f"{_BASE_DATE}T00:00:00Z",
            "as_of": f"{_BASE_DATE}T09:30:00Z",
            "org_id": _O,
        },
    ]


def gen_portfolio_greeks() -> list[dict[str, object]]:
    """Aggregated greeks per portfolio."""
    return [
        {
            "portfolio_id": "greeks-global",
            "portfolio": "global",
            "net_delta": 12.45,
            "net_gamma": 0.085,
            "net_theta": -425.30,
            "net_vega": 1850.00,
            "net_rho": 62.50,
            "delta_notional_usd": 837562.50,
            "gamma_1pct_pnl": 5720.00,
            "theta_daily_usd": -425.30,
            "vega_1vol_pnl": 1850.00,
            "as_of": f"{_BASE_DATE}T09:30:00Z",
            "org_id": _O,
        },
        {
            "portfolio_id": "greeks-acme",
            "portfolio": "acme",
            "net_delta": 3.20,
            "net_gamma": 0.022,
            "net_theta": -112.00,
            "net_vega": 480.00,
            "net_rho": 16.80,
            "delta_notional_usd": 215200.00,
            "gamma_1pct_pnl": 1480.00,
            "theta_daily_usd": -112.00,
            "vega_1vol_pnl": 480.00,
            "as_of": f"{_BASE_DATE}T09:30:00Z",
            "org_id": _A,
        },
        {
            "portfolio_id": "greeks-vertex",
            "portfolio": "vertex",
            "net_delta": 1.85,
            "net_gamma": 0.012,
            "net_theta": -65.00,
            "net_vega": 280.00,
            "net_rho": 9.40,
            "delta_notional_usd": 124437.50,
            "gamma_1pct_pnl": 808.00,
            "theta_daily_usd": -65.00,
            "vega_1vol_pnl": 280.00,
            "as_of": f"{_BASE_DATE}T09:30:00Z",
            "org_id": _V,
        },
        {
            "portfolio_id": "greeks-beta",
            "portfolio": "beta",
            "net_delta": 0.95,
            "net_gamma": 0.008,
            "net_theta": -32.00,
            "net_vega": 140.00,
            "net_rho": 4.70,
            "delta_notional_usd": 63912.50,
            "gamma_1pct_pnl": 538.00,
            "theta_daily_usd": -32.00,
            "vega_1vol_pnl": 140.00,
            "as_of": f"{_BASE_DATE}T09:30:00Z",
            "org_id": _B,
        },
    ]


def gen_risk_exposure() -> list[dict[str, object]]:
    """Per-strategy current exposure."""
    _strategies = [
        ("strat-001", "DEFI_ETH_BASIS_SCE_1H", 185000, 42000, 1.2, 154167, 95833, 0.34, _O),
        ("strat-002", "CEFI_BTC_ML_DIR_HUF_4H", 320000, 125000, 3.2, 100000, 50000, 0.64, _A),
        ("strat-003", "CEFI_ETH_OPT_MM_EVT_TICK", 210000, -15000, 2.1, 100000, 80000, 0.42, _O),
        ("strat-004", "CEFI_BTC_OPT_VOL_ARB_1H", 120000, 25000, 1.5, 80000, 120000, 0.24, _O),
        ("strat-005", "DEFI_MULTI_YIELD_AGG_4H", 95000, 95000, 1.0, 95000, 155000, 0.19, _O),
        ("strat-006", "CEFI_MULTI_ML_MOM_HUF_1H", 250000, 80000, 2.5, 100000, 60000, 0.50, _O),
        ("strat-007", "DEFI_ETH_LEND_YIELD_4H", 280000, 280000, 1.0, 280000, 20000, 0.93, _O),
        ("strat-009", "CEFI_SOL_PERP_MKT_TICK", 78000, 62000, 7.8, 10000, 5000, 0.78, _O),
        ("strat-011", "CEFI_MULTI_FUND_ARB_8H", 145000, 12000, 1.8, 80556, 69444, 0.29, _O),
        ("strat-013", "CEFI_BTC_STAT_ARB_MR_1H", 65000, 5000, 2.6, 25000, 35000, 0.42, _V),
        ("strat-014", "CEFI_MULTI_VOL_SURF_EVT_1H", 150000, -8000, 1.5, 100000, 100000, 0.30, _A),
        ("strat-016", "TRADFI_EQUITY_PAIRS", 88000, 3000, 1.1, 80000, 120000, 0.18, _B),
    ]
    records: list[dict[str, object]] = []
    for sid, name, gross, net, lev, used, avail, pct, org in _strategies:
        records.append(
            {
                "strategy_id": sid,
                "strategy_name": name,
                "gross_exposure": float(gross),
                "net_exposure": float(net),
                "leverage": lev,
                "margin_used": float(used),
                "margin_available": float(avail),
                "pct_of_limit": pct,
                "as_of": f"{_BASE_DATE}T09:30:00Z",
                "org_id": org,
            },
        )
    return records
