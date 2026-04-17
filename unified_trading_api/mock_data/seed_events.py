"""Events domain seed data — economic calendar, ML predictions, news, positions.

Mock data uses realistic April/May 2026 dates and values.
Seeded into collections:
    events_calendar     — upcoming economic events
    events_predictions  — ML impact predictions per event-instrument pair
    events_news         — recent news and macro announcements
    events_positions    — active event-driven positions
"""

from __future__ import annotations

from typing import Protocol


def generate_events_calendar() -> list[dict[str, object]]:
    """10 upcoming economic events across US, EU, JP."""
    return [
        {
            "id": "evt-fomc-2026-04",
            "name": "FOMC Interest Rate Decision",
            "event_type": "FOMC",
            "scheduled_at": "2026-04-29T18:00:00Z",
            "impact": "HIGH",
            "previous_value": "4.25%",
            "forecast": "4.25%",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
        {
            "id": "evt-nfp-2026-05",
            "name": "Non-Farm Payrolls",
            "event_type": "NFP",
            "scheduled_at": "2026-05-02T12:30:00Z",
            "impact": "HIGH",
            "previous_value": "228K",
            "forecast": "215K",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
        {
            "id": "evt-cpi-2026-05",
            "name": "CPI Year-over-Year",
            "event_type": "CPI",
            "scheduled_at": "2026-05-13T12:30:00Z",
            "impact": "HIGH",
            "previous_value": "2.8%",
            "forecast": "2.7%",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
        {
            "id": "evt-ecb-2026-04",
            "name": "ECB Interest Rate Decision",
            "event_type": "ECB",
            "scheduled_at": "2026-04-17T11:45:00Z",
            "impact": "HIGH",
            "previous_value": "2.50%",
            "forecast": "2.25%",
            "actual_value": None,
            "currency": "EUR",
            "region": "EU",
        },
        {
            "id": "evt-pce-2026-05",
            "name": "Core PCE Price Index",
            "event_type": "PCE",
            "scheduled_at": "2026-05-30T12:30:00Z",
            "impact": "HIGH",
            "previous_value": "2.6%",
            "forecast": "2.5%",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
        {
            "id": "evt-claims-2026-04",
            "name": "Initial Jobless Claims",
            "event_type": "CLAIMS",
            "scheduled_at": "2026-04-17T12:30:00Z",
            "impact": "MEDIUM",
            "previous_value": "223K",
            "forecast": "218K",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
        {
            "id": "evt-gdp-2026-q1",
            "name": "GDP Advance Estimate Q1",
            "event_type": "GDP",
            "scheduled_at": "2026-04-29T12:30:00Z",
            "impact": "HIGH",
            "previous_value": "2.3%",
            "forecast": "2.1%",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
        {
            "id": "evt-boj-2026-04",
            "name": "BOJ Interest Rate Decision",
            "event_type": "BOJ",
            "scheduled_at": "2026-04-24T03:00:00Z",
            "impact": "MEDIUM",
            "previous_value": "0.75%",
            "forecast": "0.75%",
            "actual_value": None,
            "currency": "JPY",
            "region": "JP",
        },
        {
            "id": "evt-ism-2026-05",
            "name": "ISM Manufacturing PMI",
            "event_type": "ISM",
            "scheduled_at": "2026-05-01T14:00:00Z",
            "impact": "MEDIUM",
            "previous_value": "50.3",
            "forecast": "50.8",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
        {
            "id": "evt-retail-2026-04",
            "name": "Retail Sales MoM",
            "event_type": "RETAIL_SALES",
            "scheduled_at": "2026-04-16T12:30:00Z",
            "impact": "MEDIUM",
            "previous_value": "0.6%",
            "forecast": "0.4%",
            "actual_value": None,
            "currency": "USD",
            "region": "US",
        },
    ]


def generate_events_predictions() -> list[dict[str, object]]:
    """8 ML impact predictions across events and instruments."""
    return [
        {
            "id": "pred-fomc-btc",
            "event_id": "evt-fomc-2026-04",
            "event_name": "FOMC Interest Rate Decision",
            "instrument": "BTC-USD",
            "scenario_above": {
                "label": "Rate hike surprise",
                "expected_move_pct": -4.2,
                "probability": 0.05,
            },
            "scenario_below": {
                "label": "Rate cut",
                "expected_move_pct": 6.8,
                "probability": 0.15,
            },
            "scenario_inline": {
                "label": "Hold as expected",
                "expected_move_pct": 1.2,
                "probability": 0.80,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.82,
            "updated_at": "2026-04-15T10:00:00Z",
        },
        {
            "id": "pred-fomc-eth",
            "event_id": "evt-fomc-2026-04",
            "event_name": "FOMC Interest Rate Decision",
            "instrument": "ETH-USD",
            "scenario_above": {
                "label": "Rate hike surprise",
                "expected_move_pct": -5.1,
                "probability": 0.05,
            },
            "scenario_below": {
                "label": "Rate cut",
                "expected_move_pct": 8.2,
                "probability": 0.15,
            },
            "scenario_inline": {
                "label": "Hold as expected",
                "expected_move_pct": 1.5,
                "probability": 0.80,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.78,
            "updated_at": "2026-04-15T10:00:00Z",
        },
        {
            "id": "pred-cpi-btc",
            "event_id": "evt-cpi-2026-05",
            "event_name": "CPI Year-over-Year",
            "instrument": "BTC-USD",
            "scenario_above": {
                "label": "CPI above forecast",
                "expected_move_pct": -1.5,
                "probability": 0.30,
            },
            "scenario_below": {
                "label": "CPI below forecast",
                "expected_move_pct": 2.3,
                "probability": 0.35,
            },
            "scenario_inline": {
                "label": "CPI inline",
                "expected_move_pct": 0.2,
                "probability": 0.35,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.75,
            "updated_at": "2026-04-15T10:00:00Z",
        },
        {
            "id": "pred-cpi-spy",
            "event_id": "evt-cpi-2026-05",
            "event_name": "CPI Year-over-Year",
            "instrument": "SPY",
            "scenario_above": {
                "label": "CPI above forecast",
                "expected_move_pct": -0.8,
                "probability": 0.30,
            },
            "scenario_below": {
                "label": "CPI below forecast",
                "expected_move_pct": 1.1,
                "probability": 0.35,
            },
            "scenario_inline": {
                "label": "CPI inline",
                "expected_move_pct": 0.1,
                "probability": 0.35,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.84,
            "updated_at": "2026-04-15T10:00:00Z",
        },
        {
            "id": "pred-nfp-btc",
            "event_id": "evt-nfp-2026-05",
            "event_name": "Non-Farm Payrolls",
            "instrument": "BTC-USD",
            "scenario_above": {
                "label": "NFP beats forecast",
                "expected_move_pct": -0.9,
                "probability": 0.40,
            },
            "scenario_below": {
                "label": "NFP misses forecast",
                "expected_move_pct": 1.8,
                "probability": 0.25,
            },
            "scenario_inline": {
                "label": "NFP inline",
                "expected_move_pct": 0.3,
                "probability": 0.35,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.71,
            "updated_at": "2026-04-15T10:00:00Z",
        },
        {
            "id": "pred-nfp-dxy",
            "event_id": "evt-nfp-2026-05",
            "event_name": "Non-Farm Payrolls",
            "instrument": "DXY",
            "scenario_above": {
                "label": "NFP beats forecast",
                "expected_move_pct": 0.6,
                "probability": 0.40,
            },
            "scenario_below": {
                "label": "NFP misses forecast",
                "expected_move_pct": -0.8,
                "probability": 0.25,
            },
            "scenario_inline": {
                "label": "NFP inline",
                "expected_move_pct": 0.05,
                "probability": 0.35,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.79,
            "updated_at": "2026-04-15T10:00:00Z",
        },
        {
            "id": "pred-ecb-eurusd",
            "event_id": "evt-ecb-2026-04",
            "event_name": "ECB Interest Rate Decision",
            "instrument": "EUR-USD",
            "scenario_above": {
                "label": "ECB holds",
                "expected_move_pct": -0.4,
                "probability": 0.20,
            },
            "scenario_below": {
                "label": "ECB cuts 25bps",
                "expected_move_pct": -0.7,
                "probability": 0.65,
            },
            "scenario_inline": {
                "label": "ECB cuts 50bps",
                "expected_move_pct": -1.3,
                "probability": 0.15,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.73,
            "updated_at": "2026-04-15T10:00:00Z",
        },
        {
            "id": "pred-gdp-spy",
            "event_id": "evt-gdp-2026-q1",
            "event_name": "GDP Advance Estimate Q1",
            "instrument": "SPY",
            "scenario_above": {
                "label": "GDP above forecast",
                "expected_move_pct": 0.9,
                "probability": 0.30,
            },
            "scenario_below": {
                "label": "GDP below forecast",
                "expected_move_pct": -1.2,
                "probability": 0.35,
            },
            "scenario_inline": {
                "label": "GDP inline",
                "expected_move_pct": 0.15,
                "probability": 0.35,
            },
            "model_id": "mdl-macro-impact-v3",
            "confidence": 0.77,
            "updated_at": "2026-04-15T10:00:00Z",
        },
    ]


def generate_events_news() -> list[dict[str, object]]:
    """12 recent news and macro announcement items."""
    return [
        {
            "id": "news-1",
            "title": "FOMC Minutes Signal Patience on Rate Cuts Amid Sticky Services Inflation",
            "source": "Bloomberg",
            "published_at": "2026-04-15T14:30:00Z",
            "sentiment": "bearish",
            "category": "macro",
            "instruments": ["BTC-USD", "SPY", "TLT"],
            "summary": "Minutes from the March meeting revealed most members want to see further"
            " disinflation in services before easing.",
        },
        {
            "id": "news-2",
            "title": "Ethereum Gas Fees Drop to Sub-$0.01 After Pectra Upgrade",
            "source": "CoinDesk",
            "published_at": "2026-04-15T12:15:00Z",
            "sentiment": "bullish",
            "category": "on-chain",
            "instruments": ["ETH-USD", "ETH-USDT"],
            "summary": "The Pectra upgrade has reduced average L2 gas fees to under 1 cent,"
            " driving a 40% increase in daily active addresses on Arbitrum and Base.",
        },
        {
            "id": "news-3",
            "title": "China PMI Contracts for Third Straight Month",
            "source": "Reuters",
            "published_at": "2026-04-15T10:00:00Z",
            "sentiment": "bearish",
            "category": "macro",
            "instruments": ["SPY", "FXI", "COPPER"],
            "summary": "Caixin Manufacturing PMI came in at 48.9, below the 50 expansion"
            " threshold, signalling continued weakness in China's factory sector.",
        },
        {
            "id": "news-4",
            "title": "MakerDAO Approves RWA Vault Expansion to $5B",
            "source": "The Block",
            "published_at": "2026-04-15T08:45:00Z",
            "sentiment": "bullish",
            "category": "governance",
            "instruments": ["MKR-USD", "DAI-USD"],
            "summary": "MakerDAO governance voted to expand RWA vault allocations to $5B in"
            " US Treasuries, further bridging DeFi and TradFi yield.",
        },
        {
            "id": "news-5",
            "title": "US Treasury 10Y Yield Climbs to 4.85% on Hot Retail Sales",
            "source": "Bloomberg",
            "published_at": "2026-04-14T18:30:00Z",
            "sentiment": "bearish",
            "category": "macro",
            "instruments": ["TLT", "SPY", "BTC-USD"],
            "summary": "March retail sales rose 0.7% MoM vs 0.4% expected, pushing 10Y yields"
            " to 4.85% and pressuring risk assets.",
        },
        {
            "id": "news-6",
            "title": "Uniswap Foundation Launches $50M Grants for V4 Hook Developers",
            "source": "CoinDesk",
            "published_at": "2026-04-14T16:00:00Z",
            "sentiment": "bullish",
            "category": "governance",
            "instruments": ["UNI-USD", "ETH-USD"],
            "summary": "The Uniswap Foundation announced a $50M grant programme to incentivise"
            " development of custom V4 hooks, targeting institutional use cases.",
        },
        {
            "id": "news-7",
            "title": "Binance Halts SOL Withdrawals During Network Congestion Event",
            "source": "The Block",
            "published_at": "2026-04-14T13:20:00Z",
            "sentiment": "bearish",
            "category": "exchange",
            "instruments": ["SOL-USD", "SOL-USDT"],
            "summary": "A surge in memecoin minting caused Solana TPS to spike to 65K,"
            " triggering temporary withdrawal halts on Binance and OKX.",
        },
        {
            "id": "news-8",
            "title": "BlackRock iShares Bitcoin ETF Sees Record $1.2B Daily Inflow",
            "source": "Bloomberg",
            "published_at": "2026-04-14T10:45:00Z",
            "sentiment": "bullish",
            "category": "institutional",
            "instruments": ["BTC-USD", "IBIT"],
            "summary": "IBIT attracted $1.2B in a single day, the largest daily inflow since"
            " launch. Total AUM now exceeds $85B.",
        },
        {
            "id": "news-9",
            "title": "ECB's Lagarde Hints at April Rate Cut in Speech",
            "source": "Reuters",
            "published_at": "2026-04-14T08:00:00Z",
            "sentiment": "bullish",
            "category": "macro",
            "instruments": ["EUR-USD", "EUROSTOXX"],
            "summary": "ECB President Lagarde noted inflation is on a credible path toward 2%"
            " and the April meeting will assess whether conditions warrant a rate adjustment.",
        },
        {
            "id": "news-10",
            "title": "Liverpool Beat Real Madrid 3-1 in Champions League Quarter-Final",
            "source": "ESPN",
            "published_at": "2026-04-13T22:00:00Z",
            "sentiment": "neutral",
            "category": "sports",
            "instruments": ["UCL-QF-1"],
            "summary": "Liverpool dominate at Anfield with goals from Salah (2) and Diaz."
            " Outright winner markets shift heavily toward Liverpool.",
        },
        {
            "id": "news-11",
            "title": "Aave V3 Arbitrum Reaches $8B in Total Value Locked",
            "source": "DeFi Llama",
            "published_at": "2026-04-13T15:30:00Z",
            "sentiment": "bullish",
            "category": "on-chain",
            "instruments": ["AAVE-USD", "ARB-USD"],
            "summary": "Aave V3 on Arbitrum surpassed $8B TVL, driven by institutional demand"
            " for on-chain lending with sub-second finality.",
        },
        {
            "id": "news-12",
            "title": "US Senate Advances Stablecoin Regulation Bill",
            "source": "Reuters",
            "published_at": "2026-04-13T12:00:00Z",
            "sentiment": "neutral",
            "category": "regulatory",
            "instruments": ["USDT-USD", "USDC-USD"],
            "summary": "The Clarity for Payment Stablecoins Act passed the Senate Banking"
            " Committee 14-9, setting the stage for a full floor vote in May.",
        },
    ]


def generate_events_positions() -> list[dict[str, object]]:
    """6 active event-driven positions."""
    return [
        {
            "id": "epos-1",
            "event_id": "evt-fomc-2026-04",
            "event_name": "FOMC Rate Decision",
            "instrument": "BTC-PERP",
            "direction": "LONG",
            "entry_price": 91_250.0,
            "current_price": 92_480.0,
            "size": 2.5,
            "pnl_usd": 3_075.0,
            "phase": "PRE_EVENT",
            "strategy_id": "strat-macro-event-v2",
            "opened_at": "2026-04-14T09:00:00Z",
        },
        {
            "id": "epos-2",
            "event_id": "evt-ecb-2026-04",
            "event_name": "ECB Rate Decision",
            "instrument": "EUR-USD",
            "direction": "SHORT",
            "entry_price": 1.0892,
            "current_price": 1.0845,
            "size": 500_000.0,
            "pnl_usd": 2_350.0,
            "phase": "PRE_EVENT",
            "strategy_id": "strat-macro-event-v2",
            "opened_at": "2026-04-14T11:30:00Z",
        },
        {
            "id": "epos-3",
            "event_id": "evt-cpi-2026-05",
            "event_name": "CPI Release",
            "instrument": "TLT",
            "direction": "LONG",
            "entry_price": 88.4,
            "current_price": 87.9,
            "size": 1_200.0,
            "pnl_usd": -600.0,
            "phase": "PRE_EVENT",
            "strategy_id": "strat-macro-event-v2",
            "opened_at": "2026-04-15T08:00:00Z",
        },
        {
            "id": "epos-4",
            "event_id": "evt-retail-2026-04",
            "event_name": "Retail Sales MoM",
            "instrument": "SPY",
            "direction": "SHORT",
            "entry_price": 542.1,
            "current_price": 538.6,
            "size": 200.0,
            "pnl_usd": 700.0,
            "phase": "POST_EVENT",
            "strategy_id": "strat-macro-event-v2",
            "opened_at": "2026-04-16T12:35:00Z",
        },
        {
            "id": "epos-5",
            "event_id": "evt-fomc-2026-04",
            "event_name": "FOMC Rate Decision",
            "instrument": "ETH-PERP",
            "direction": "LONG",
            "entry_price": 3_420.0,
            "current_price": 3_485.0,
            "size": 15.0,
            "pnl_usd": 975.0,
            "phase": "PRE_EVENT",
            "strategy_id": "strat-macro-event-v2",
            "opened_at": "2026-04-14T09:15:00Z",
        },
        {
            "id": "epos-6",
            "event_id": "evt-nfp-2026-05",
            "event_name": "Non-Farm Payrolls",
            "instrument": "DXY",
            "direction": "SHORT",
            "entry_price": 104.8,
            "current_price": 104.52,
            "size": 100_000.0,
            "pnl_usd": 267.0,
            "phase": "PRE_EVENT",
            "strategy_id": "strat-macro-event-v2",
            "opened_at": "2026-04-15T14:00:00Z",
        },
    ]


def seed_events(store: object) -> None:
    """Seed events domain into MockStateStore."""

    class _Seedable(Protocol):
        def seed(self, collection: str, items: list[dict[str, object]]) -> None: ...

    _store: _Seedable = store  # type: ignore[assignment]
    _store.seed("events_calendar", generate_events_calendar())
    _store.seed("events_predictions", generate_events_predictions())
    _store.seed("events_news", generate_events_news())
    _store.seed("events_positions", generate_events_positions())
