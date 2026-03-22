"""Phase 8 domain-specific seed data.

Generates risk limits, options chain, vol surfaces, VaR metrics, FX rates,
regulatory reports, news items, and DeFi health fields.  All computations
use the ``math`` stdlib — no scipy / numpy required.
"""

from __future__ import annotations

import math
from typing import Final

# ── Org constants (mirror seed.py) ────────────────────────────────────
_O: Final[str] = "odum-internal"
_A: Final[str] = "acme"
_V: Final[str] = "vertex"
_B: Final[str] = "beta"

# ── Reference date ────────────────────────────────────────────────────
_BASE_DATE: Final[str] = "2026-03-22"
_BASE_TS: Final[str] = "2026-03-22T00:00:00Z"

# ── Underlying spot prices ───────────────────────────────────────────
_BTC_SPOT: Final[float] = 67_000.0
_ETH_SPOT: Final[float] = 3_500.0
_SPY_SPOT: Final[float] = 520.0

# ── Risk-free rate for Black-Scholes ─────────────────────────────────
_R: Final[float] = 0.045


# ══════════════════════════════════════════════════════════════════════
#  Black-Scholes helpers (stdlib math only)
# ══════════════════════════════════════════════════════════════════════


def _norm_cdf(x: float) -> float:
    """Standard-normal CDF via math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard-normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bs_greeks(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    is_call: bool,
) -> dict[str, float]:
    """Return price + Greeks for a European option (no dividends)."""
    sqrt_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (_R + 0.5 * iv * iv) * t_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t

    nd1 = _norm_cdf(d1)
    nd2 = _norm_cdf(d2)
    npd1 = _norm_pdf(d1)

    if is_call:
        price = spot * nd1 - strike * math.exp(-_R * t_years) * nd2
        delta = nd1
    else:
        price = strike * math.exp(-_R * t_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        delta = nd1 - 1.0

    gamma = npd1 / (spot * iv * sqrt_t)
    vega = spot * npd1 * sqrt_t / 100.0  # per 1% IV move
    theta = (
        -(spot * npd1 * iv) / (2.0 * sqrt_t)
        - _R * strike * math.exp(-_R * t_years) * (nd2 if is_call else _norm_cdf(-d2))
    ) / 365.0

    return {
        "price": round(price, 4),
        "delta": round(delta, 6),
        "gamma": round(gamma, 8),
        "vega": round(vega, 4),
        "theta": round(theta, 4),
    }


# ══════════════════════════════════════════════════════════════════════
#  Generators per collection
# ══════════════════════════════════════════════════════════════════════


def _gen_risk_limits() -> list[dict[str, object]]:
    """Per-strategy risk limits (strat-001..strat-050)."""
    # Named profiles keyed by prefix-match on strategy ID.
    profiles: list[dict[str, object]] = [
        # Momentum strategies
        {
            "ids": ["strat-002", "strat-006", "strat-009", "strat-011"],
            "max_position_size_usd": 500_000.0,
            "max_leverage": 3.0,
            "max_var_99": 0.05,
            "max_exposure_pct": 0.15,
            "max_open_orders": 50,
            "profile": "momentum",
        },
        # Market-making
        {
            "ids": ["strat-003", "strat-004", "strat-014", "strat-017"],
            "max_position_size_usd": 2_000_000.0,
            "max_leverage": 10.0,
            "max_var_99": 0.03,
            "max_exposure_pct": 0.25,
            "max_open_orders": 200,
            "profile": "market_making",
        },
        # DeFi yield
        {
            "ids": ["strat-001", "strat-007", "strat-010", "strat-015"],
            "max_position_size_usd": 200_000.0,
            "max_leverage": 1.5,
            "max_var_99": 0.02,
            "max_exposure_pct": 0.08,
            "max_open_orders": 10,
            "profile": "defi_yield",
        },
        # TradFi stat-arb
        {
            "ids": ["strat-005", "strat-013"],
            "max_position_size_usd": 1_000_000.0,
            "max_leverage": 5.0,
            "max_var_99": 0.04,
            "max_exposure_pct": 0.20,
            "max_open_orders": 80,
            "profile": "stat_arb",
        },
        # Sports / prediction
        {
            "ids": ["strat-008", "strat-012", "strat-016", "strat-018"],
            "max_position_size_usd": 100_000.0,
            "max_leverage": 1.0,
            "max_var_99": 0.10,
            "max_exposure_pct": 0.05,
            "max_open_orders": 30,
            "profile": "event",
        },
    ]

    # Build explicit records for named strategies
    records: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for prof in profiles:
        raw_ids = prof["ids"]
        ids: list[str] = list(raw_ids) if isinstance(raw_ids, list) else []
        for sid in ids:
            seen_ids.add(sid)
            # Make strat-004 and strat-007 close to limit for demo impact
            exposure_pct = prof["max_exposure_pct"]
            if sid == "strat-004":
                exposure_pct = float(str(prof["max_exposure_pct"])) * 0.95
            elif sid == "strat-007":
                exposure_pct = float(str(prof["max_exposure_pct"])) * 0.92
            records.append(
                {
                    "strategy_id": sid,
                    "profile": prof["profile"],
                    "max_position_size_usd": prof["max_position_size_usd"],
                    "max_leverage": prof["max_leverage"],
                    "max_var_99": prof["max_var_99"],
                    "max_exposure_pct": exposure_pct,
                    "max_open_orders": prof["max_open_orders"],
                    "org_id": _O,
                    "updated_at": _BASE_TS,
                }
            )

    # Fill strat-019..strat-050 with generic defaults
    for i in range(19, 51):
        sid = f"strat-{i:03d}"
        if sid not in seen_ids:
            records.append(
                {
                    "strategy_id": sid,
                    "profile": "generic",
                    "max_position_size_usd": 300_000.0,
                    "max_leverage": 2.0,
                    "max_var_99": 0.04,
                    "max_exposure_pct": 0.12,
                    "max_open_orders": 40,
                    "org_id": [_O, _A, _V, _B][i % 4],
                    "updated_at": _BASE_TS,
                }
            )

    return records


def _gen_options_chain() -> list[dict[str, object]]:
    """BTC / ETH / SPY options with Black-Scholes Greeks."""
    expiry_days: list[int] = [7, 14, 30, 60, 90]
    records: list[dict[str, object]] = []
    opt_counter = 0

    underlyings: list[tuple[str, float, float, int, float]] = [
        # (symbol, spot, atm_iv, n_strikes, strike_step_pct)
        ("BTC", _BTC_SPOT, 0.45, 10, 0.05),
        ("ETH", _ETH_SPOT, 0.55, 5, 0.05),
        ("SPY", _SPY_SPOT, 0.15, 5, 0.02),
    ]

    for symbol, spot, atm_iv, n_strikes, step in underlyings:
        # Strike range: centred around spot
        half = n_strikes // 2
        strikes: list[float] = []
        for k in range(-half, half + 1):
            if k == 0 and n_strikes % 2 == 0:
                continue
            raw = spot * (1.0 + k * step)
            strikes.append(round(raw, 2))
        # Trim to exact n_strikes if needed
        strikes = strikes[:n_strikes]

        for exp_d in expiry_days:
            t_years = exp_d / 365.0
            for strike in strikes:
                moneyness = strike / spot
                # IV skew: lower strikes get higher IV
                skew = atm_iv * (1.0 + 0.12 * (1.0 - moneyness))
                iv = max(0.05, round(skew, 4))

                for is_call in (True, False):
                    opt_counter += 1
                    greeks = _bs_greeks(spot, strike, t_years, iv, is_call)
                    records.append(
                        {
                            "option_id": f"opt-{symbol.lower()}-{opt_counter:05d}",
                            "underlying": symbol,
                            "spot_price": spot,
                            "strike": strike,
                            "expiry_days": exp_d,
                            "expiry_date": (
                                f"2026-{(3 + exp_d // 30):02d}-{min(22 + exp_d % 30, 28):02d}"
                            ),
                            "option_type": "call" if is_call else "put",
                            "implied_volatility": iv,
                            "price": greeks["price"],
                            "delta": greeks["delta"],
                            "gamma": greeks["gamma"],
                            "vega": greeks["vega"],
                            "theta": greeks["theta"],
                            "open_interest": 1200 - opt_counter % 400,
                            "volume_24h": 350 + (opt_counter * 17) % 600,
                            "org_id": _O,
                        }
                    )

    return records


def _gen_vol_surfaces() -> list[dict[str, object]]:
    """Per-underlying volatility surfaces."""
    surfaces: list[dict[str, object]] = []
    configs: list[tuple[str, float, float, float, float, float]] = [
        # (symbol, atm_iv, skew_25d, butterfly_25d, rr_25d, spot)
        ("BTC", 0.45, -0.05, 0.02, -0.04, _BTC_SPOT),
        ("ETH", 0.55, -0.06, 0.025, -0.05, _ETH_SPOT),
        ("SPY", 0.15, -0.03, 0.01, -0.025, _SPY_SPOT),
    ]

    expiry_slices: list[int] = [7, 30, 60, 90]

    for idx, (symbol, atm_iv, skew_25d, butterfly_25d, rr_25d, spot) in enumerate(configs):
        slices: list[dict[str, object]] = []
        for exp_d in expiry_slices:
            # Term structure: longer expiry → slightly higher ATM IV
            term_adj = 1.0 + 0.002 * (exp_d - 30)
            slice_atm = round(atm_iv * term_adj, 4)

            smile: list[dict[str, float]] = []
            for delta_pct in range(-20, 25, 5):
                strike = round(spot * (1.0 + delta_pct * 0.01), 2)
                moneyness = strike / spot
                iv_point = slice_atm * (1.0 + 0.12 * (1.0 - moneyness))
                smile.append({"strike": strike, "iv": round(iv_point, 4)})

            slices.append(
                {
                    "expiry_days": exp_d,
                    "atm_iv": slice_atm,
                    "smile": smile,
                }
            )

        term_structure: list[dict[str, float]] = [
            {"expiry_days": float(d), "atm_iv": round(atm_iv * (1.0 + 0.002 * (d - 30)), 4)}
            for d in expiry_slices
        ]

        surfaces.append(
            {
                "surface_id": f"vol-surf-{symbol.lower()}-{idx + 1:03d}",
                "underlying": symbol,
                "spot_price": spot,
                "as_of": _BASE_TS,
                "atm_iv": atm_iv,
                "skew_25d": skew_25d,
                "butterfly_25d": butterfly_25d,
                "risk_reversal_25d": rr_25d,
                "slices": slices,
                "term_structure": term_structure,
                "org_id": _O,
            }
        )

    return surfaces


def _gen_var_metrics() -> list[dict[str, object]]:
    """Per-strategy Value-at-Risk metrics."""
    # (strategy_id, profile, hist_var, param_var, cvar, cf_var, org)
    entries: list[tuple[str, str, float, float, float, float, str]] = [
        ("strat-002", "momentum", 0.035, 0.032, 0.048, 0.038, _O),
        ("strat-006", "momentum", 0.042, 0.040, 0.055, 0.045, _O),
        ("strat-009", "momentum", 0.028, 0.026, 0.038, 0.030, _O),
        ("strat-011", "momentum", 0.050, 0.047, 0.065, 0.053, _O),
        ("strat-003", "market_making", 0.018, 0.016, 0.025, 0.020, _O),
        ("strat-004", "market_making", 0.022, 0.020, 0.030, 0.024, _A),
        ("strat-014", "market_making", 0.015, 0.014, 0.021, 0.017, _A),
        ("strat-001", "defi_yield", 0.012, 0.010, 0.018, 0.014, _O),
        ("strat-007", "defi_yield", 0.008, 0.007, 0.012, 0.009, _O),
        ("strat-010", "defi_yield", 0.015, 0.013, 0.020, 0.016, _V),
        ("strat-005", "stat_arb", 0.025, 0.023, 0.034, 0.027, _V),
        ("strat-013", "stat_arb", 0.030, 0.028, 0.040, 0.032, _B),
        ("strat-008", "event", 0.060, 0.055, 0.080, 0.065, _O),
        ("strat-012", "event", 0.070, 0.065, 0.092, 0.075, _O),
        ("strat-018", "prediction", 0.045, 0.042, 0.060, 0.048, _O),
    ]

    return [
        {
            "strategy_id": sid,
            "profile": profile,
            "historical_var_99": hist,
            "parametric_var_99": param,
            "cvar_99": cvar,
            "cornish_fisher_var_99": cf,
            "confidence_level": 0.99,
            "lookback_days": 252,
            "as_of": _BASE_TS,
            "org_id": org,
        }
        for sid, profile, hist, param, cvar, cf, org in entries
    ]


def _gen_stress_test_results() -> list[dict[str, object]]:
    """Stress-test scenario results."""
    return [
        {
            "scenario_id": "stress-gfc-2008",
            "scenario_name": "GFC_2008",
            "description": "2008 Global Financial Crisis replay on current portfolio",
            "portfolio_impact_pct": -0.15,
            "expected_loss_usd": -4_500_000.0,
            "worst_strategy_id": "strat-005",
            "worst_strategy_loss_pct": -0.28,
            "recovery_days_est": 180,
            "as_of": _BASE_TS,
            "org_id": _O,
        },
        {
            "scenario_id": "stress-covid-2020",
            "scenario_name": "COVID_2020",
            "description": "March 2020 COVID crash replay on current portfolio",
            "portfolio_impact_pct": -0.10,
            "expected_loss_usd": -3_000_000.0,
            "worst_strategy_id": "strat-006",
            "worst_strategy_loss_pct": -0.22,
            "recovery_days_est": 90,
            "as_of": _BASE_TS,
            "org_id": _O,
        },
        {
            "scenario_id": "stress-crypto-black-thurs",
            "scenario_name": "CRYPTO_BLACK_THURSDAY",
            "description": "March 2020 BTC 50% single-day crash on current portfolio",
            "portfolio_impact_pct": -0.25,
            "expected_loss_usd": -7_500_000.0,
            "worst_strategy_id": "strat-002",
            "worst_strategy_loss_pct": -0.45,
            "recovery_days_est": 120,
            "as_of": _BASE_TS,
            "org_id": _O,
        },
    ]


def _gen_correlation_matrix() -> list[dict[str, object]]:
    """NxN correlation matrix for the first 10 strategies."""
    labels: list[str] = [f"strat-{i:03d}" for i in range(1, 11)]
    n = len(labels)

    # Deterministic correlation bands:
    # crypto-crypto ~0.5-0.7, tradfi-tradfi ~0.2-0.4, cross ~0.0-0.15
    crypto_ids = {0, 1, 2, 3, 5, 8}  # indices of crypto strategies
    tradfi_ids = {4}  # strat-005
    defi_ids = {6, 9}  # strat-007, strat-010
    sports_ids = {7}  # strat-008

    matrix: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            elif i > j:
                row.append(matrix[j][i])  # symmetric
            else:
                # Determine correlation based on category overlap
                both_crypto = i in crypto_ids and j in crypto_ids
                both_defi = i in defi_ids and j in defi_ids
                crypto_defi = (i in crypto_ids and j in defi_ids) or (
                    i in defi_ids and j in crypto_ids
                )
                either_sports = i in sports_ids or j in sports_ids
                either_tradfi = i in tradfi_ids or j in tradfi_ids

                if both_crypto:
                    base = 0.50 + 0.02 * ((i + j) % 10)
                elif both_defi:
                    base = 0.55 + 0.01 * ((i + j) % 5)
                elif crypto_defi:
                    base = 0.35 + 0.01 * ((i * j) % 8)
                elif either_tradfi and (i in crypto_ids or j in crypto_ids):
                    base = 0.20 + 0.02 * ((i + j) % 5)
                elif either_sports:
                    base = 0.02 + 0.01 * ((i + j) % 4)
                else:
                    base = 0.15 + 0.01 * ((i + j) % 6)

                row.append(round(min(base, 0.95), 3))
        matrix.append(row)

    return [
        {
            "matrix_id": "corr-matrix-001",
            "labels": labels,
            "matrix": matrix,
            "method": "pearson",
            "lookback_days": 252,
            "as_of": _BASE_TS,
            "org_id": _O,
        }
    ]


def _gen_fx_rates() -> list[dict[str, object]]:
    """Static FX rates."""
    rates: list[tuple[str, float, str]] = [
        ("BTC/USD", 67_000.0, "crypto"),
        ("ETH/USD", 3_500.0, "crypto"),
        ("USDT/USD", 1.0001, "stablecoin"),
        ("EUR/USD", 1.08, "fiat"),
        ("GBP/USD", 1.27, "fiat"),
        ("KRW/USD", 0.00075, "fiat"),
    ]
    return [
        {
            "pair": pair,
            "rate": rate,
            "category": cat,
            "source": "internal_aggregator",
            "as_of": _BASE_TS,
            "org_id": _O,
        }
        for pair, rate, cat in rates
    ]


def _gen_regulatory_reports() -> list[dict[str, object]]:
    """Regulatory filing records."""
    return [
        {
            "report_id": "reg-mifid-001",
            "report_type": "MiFID_II_BEST_EXECUTION",
            "jurisdiction": "EU",
            "status": "submitted",
            "filing_date": "2026-03-15",
            "next_due_date": "2026-06-15",
            "instruments_covered": 42,
            "filing_reference": "MIFID-2026-Q1-001",
            "org_id": _O,
        },
        {
            "report_id": "reg-mifid-002",
            "report_type": "MiFID_II_BEST_EXECUTION",
            "jurisdiction": "EU",
            "status": "submitted",
            "filing_date": "2026-03-01",
            "next_due_date": "2026-06-01",
            "instruments_covered": 38,
            "filing_reference": "MIFID-2026-Q1-002",
            "org_id": _A,
        },
        {
            "report_id": "reg-mifid-003",
            "report_type": "MiFID_II_BEST_EXECUTION",
            "jurisdiction": "EU",
            "status": "submitted",
            "filing_date": "2026-02-28",
            "next_due_date": "2026-05-28",
            "instruments_covered": 15,
            "filing_reference": "MIFID-2026-Q1-003",
            "org_id": _V,
        },
        {
            "report_id": "reg-fca-001",
            "report_type": "FCA_TRANSACTION_REPORT",
            "jurisdiction": "UK",
            "status": "submitted",
            "filing_date": "2026-03-18",
            "next_due_date": "2026-04-18",
            "instruments_covered": 28,
            "filing_reference": "FCA-TR-2026-03-001",
            "org_id": _O,
        },
        {
            "report_id": "reg-fca-002",
            "report_type": "FCA_TRANSACTION_REPORT",
            "jurisdiction": "UK",
            "status": "submitted",
            "filing_date": "2026-03-10",
            "next_due_date": "2026-04-10",
            "instruments_covered": 19,
            "filing_reference": "FCA-TR-2026-03-002",
            "org_id": _A,
        },
        {
            "report_id": "reg-emir-001",
            "report_type": "EMIR_TRADE_REPORT",
            "jurisdiction": "EU",
            "status": "pending",
            "filing_date": "",
            "next_due_date": "2026-03-25",
            "instruments_covered": 35,
            "filing_reference": "",
            "org_id": _O,
        },
        {
            "report_id": "reg-emir-002",
            "report_type": "EMIR_TRADE_REPORT",
            "jurisdiction": "EU",
            "status": "pending",
            "filing_date": "",
            "next_due_date": "2026-03-28",
            "instruments_covered": 22,
            "filing_reference": "",
            "org_id": _V,
        },
        {
            "report_id": "reg-fca-003",
            "report_type": "FCA_TRANSACTION_REPORT",
            "jurisdiction": "UK",
            "status": "overdue",
            "filing_date": "",
            "next_due_date": "2026-03-15",
            "instruments_covered": 11,
            "filing_reference": "",
            "org_id": _B,
        },
        {
            "report_id": "reg-mifid-004",
            "report_type": "MiFID_II_RTS_28",
            "jurisdiction": "EU",
            "status": "submitted",
            "filing_date": "2026-03-20",
            "next_due_date": "2026-06-20",
            "instruments_covered": 50,
            "filing_reference": "MIFID-RTS28-2026-001",
            "org_id": _O,
        },
        {
            "report_id": "reg-emir-003",
            "report_type": "EMIR_MARGIN_REPORT",
            "jurisdiction": "EU",
            "status": "submitted",
            "filing_date": "2026-03-19",
            "next_due_date": "2026-04-19",
            "instruments_covered": 30,
            "filing_reference": "EMIR-MR-2026-03-001",
            "org_id": _O,
        },
    ]


def _gen_news() -> list[dict[str, object]]:
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


def _gen_regime() -> list[dict[str, object]]:
    """Current market regime (single record)."""
    return [
        {
            "regime_id": "regime-current",
            "regime": "normal",
            "multiplier": 1.0,
            "vol_signal": 0.02,
            "correlation_signal": 0.3,
            "drawdown_velocity": -0.005,
            "as_of": _BASE_TS,
            "org_id": _O,
        }
    ]


# ══════════════════════════════════════════════════════════════════════
#  MARKET REGIME
# ══════════════════════════════════════════════════════════════════════


def _gen_market_regime() -> list[dict[str, object]]:
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


# ══════════════════════════════════════════════════════════════════════
#  PORTFOLIO GREEKS — aggregated per portfolio
# ══════════════════════════════════════════════════════════════════════


def _gen_portfolio_greeks() -> list[dict[str, object]]:
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


# ══════════════════════════════════════════════════════════════════════
#  RISK EXPOSURE — per-strategy current exposure
# ══════════════════════════════════════════════════════════════════════


def _gen_risk_exposure() -> list[dict[str, object]]:
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


# ══════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════


def generate_phase8_data() -> dict[str, list[dict[str, object]]]:
    """Return all Phase 8 seed collections keyed by domain name."""
    return {
        "risk_limits": _gen_risk_limits(),
        "options_chain": _gen_options_chain(),
        "vol_surfaces": _gen_vol_surfaces(),
        "var_metrics": _gen_var_metrics(),
        "stress_test_results": _gen_stress_test_results(),
        "correlation_matrix": _gen_correlation_matrix(),
        "fx_rates": _gen_fx_rates(),
        "regulatory_reports": _gen_regulatory_reports(),
        "news": _gen_news(),
        "regime": _gen_regime(),
        "market_regime": _gen_market_regime(),
        "portfolio_greeks": _gen_portfolio_greeks(),
        "risk_exposure": _gen_risk_exposure(),
    }
