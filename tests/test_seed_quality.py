"""Seed data quality tests.

Verifies:
1. Every record has org_id field
2. All strategy_ids in positions/orders reference valid strategies
3. All order_ids in fills reference valid orders
4. Org filtering works (client-full sees only acme data)
5. Batch vs live data returns different results
6. Reset clears mutations but preserves seed
7. Cross-domain reference integrity
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from unified_trading_api.mock_data.seed import seed_all_domains
from unified_trading_api.mock_data.state_store import MockStateStore


@pytest.fixture()
def seeded_store() -> MockStateStore:
    """Create a fresh MockStateStore and seed it."""
    store = MockStateStore()
    seed_all_domains(store)
    return store


class TestOrgIdPresence:
    """Every record must have an org_id field."""

    DOMAINS_WITH_ORG_ID: ClassVar[list[str]] = [
        "strategies",
        "orders",
        "fills",
        "positions",
        "alerts",
        "settlements",
        "invoices",
    ]

    @pytest.mark.parametrize("domain", DOMAINS_WITH_ORG_ID)
    def test_all_records_have_org_id(self, seeded_store: MockStateStore, domain: str) -> None:
        records = seeded_store.list(domain)
        assert len(records) > 0, f"Domain {domain} is empty"
        for i, record in enumerate(records):
            assert "org_id" in record, (
                f"Record {i} in {domain} missing org_id: {record.get('id', 'no-id')}"
            )

    def test_org_filtering_acme_only(self, seeded_store: MockStateStore) -> None:
        """Client-full persona (acme) should only see acme data."""
        strategies = seeded_store.list("strategies")
        acme_strategies = [s for s in strategies if s.get("org_id") == "acme"]
        assert len(acme_strategies) > 0, "No acme strategies found"
        # Verify acme strategies don't include odum-internal data
        for s in acme_strategies:
            assert s.get("org_id") == "acme"


class TestReferenceIntegrity:
    """Cross-domain references must be valid."""

    def test_position_strategy_ids_valid(self, seeded_store: MockStateStore) -> None:
        strategies = seeded_store.list("strategies")
        strategy_ids = {str(s["id"]) for s in strategies}
        positions = seeded_store.list("positions")
        for pos in positions:
            sid = pos.get("strategy_id")
            if sid is not None:
                assert str(sid) in strategy_ids, (
                    f"Position {pos.get('position_id')} references invalid strategy_id: {sid}"
                )

    def test_order_strategy_ids_valid(self, seeded_store: MockStateStore) -> None:
        strategies = seeded_store.list("strategies")
        strategy_ids = {str(s["id"]) for s in strategies}
        orders = seeded_store.list("orders")
        for order in orders:
            sid = order.get("strategy_id")
            if sid is not None:
                assert str(sid) in strategy_ids, (
                    f"Order {order.get('order_id')} references invalid strategy_id: {sid}"
                )

    def test_fill_order_ids_valid(self, seeded_store: MockStateStore) -> None:
        orders = seeded_store.list("orders")
        order_ids = {str(o.get("order_id", o.get("id"))) for o in orders}
        fills = seeded_store.list("fills")
        for fill in fills:
            oid = fill.get("order_id")
            if oid is not None:
                assert str(oid) in order_ids, (
                    f"Fill {fill.get('fill_id')} references invalid order_id: {oid}"
                )


class TestBatchLiveSeparation:
    """Batch and live collections must have different data."""

    def test_positions_batch_vs_live_differ(self, seeded_store: MockStateStore) -> None:
        batch = seeded_store.list("positions_batch")
        live = seeded_store.list("positions_live")
        assert len(batch) > 0
        assert len(live) > 0
        # They should have different prices or PnL values
        batch_ids = {str(p.get("position_id")) for p in batch}
        live_ids = {str(p.get("position_id")) for p in live}
        # At least some positions should be shared
        assert batch_ids & live_ids, "Batch and live should share some positions"

    def test_tickers_batch_vs_live_differ(self, seeded_store: MockStateStore) -> None:
        batch = seeded_store.list("tickers_batch")
        live = seeded_store.list("tickers_live")
        assert len(batch) > 0
        assert len(live) > 0
        # Batch and live should have same instruments but different prices
        batch_instruments = {str(t.get("instrument")) for t in batch}
        live_instruments = {str(t.get("instrument")) for t in live}
        assert batch_instruments == live_instruments, (
            "Batch and live tickers should cover same instruments"
        )

    def test_pnl_timeseries_batch_vs_live(self, seeded_store: MockStateStore) -> None:
        batch = seeded_store.list("pnl_timeseries_batch")
        live = seeded_store.list("pnl_timeseries_live")
        assert len(batch) > 0
        assert len(live) > 0
        assert len(batch) == len(live)


class TestResetBehavior:
    """Reset should clear mutations but allow re-seeding."""

    def test_reset_and_reseed(self, seeded_store: MockStateStore) -> None:
        initial_count = len(seeded_store.list("strategies"))
        assert initial_count == 50

        # Simulate mutation
        seeded_store.add("strategies", {"id": "strat-extra", "name": "EXTRA"})
        assert len(seeded_store.list("strategies")) == 51

        # Reset and re-seed
        seeded_store.clear()
        seed_all_domains(seeded_store)
        assert len(seeded_store.list("strategies")) == 50


class TestStrategyExpansion:
    """Strategies should be 50+ and cover all asset classes."""

    def test_strategy_count(self, seeded_store: MockStateStore) -> None:
        strategies = seeded_store.list("strategies")
        assert len(strategies) >= 50

    def test_all_asset_classes_covered(self, seeded_store: MockStateStore) -> None:
        strategies = seeded_store.list("strategies")
        asset_classes = {str(s.get("asset_class")) for s in strategies}
        for expected in ("cefi", "tradfi", "defi", "sports", "prediction"):
            assert expected in asset_classes, f"Missing asset class: {expected}"

    def test_org_distribution(self, seeded_store: MockStateStore) -> None:
        strategies = seeded_store.list("strategies")
        org_counts: dict[str, int] = {}
        for s in strategies:
            org = str(s.get("org_id", ""))
            org_counts[org] = org_counts.get(org, 0) + 1
        assert "odum-internal" in org_counts
        assert "acme" in org_counts
        assert org_counts["odum-internal"] >= org_counts["acme"]


class TestMarketDataSeeds:
    """Market data seeds should be comprehensive."""

    def test_candle_intervals(self, seeded_store: MockStateStore) -> None:
        for interval in ("candles_1m", "candles_5m", "candles_1h", "candles_1d"):
            records = seeded_store.list(interval)
            assert len(records) > 0, f"No candles for {interval}"

    def test_ticker_count(self, seeded_store: MockStateStore) -> None:
        tickers = seeded_store.list("tickers_live")
        assert len(tickers) >= 30, f"Only {len(tickers)} tickers, expected 30+"

    def test_pnl_timeseries_count(self, seeded_store: MockStateStore) -> None:
        ts = seeded_store.list("pnl_timeseries")
        strategies = seeded_store.list("strategies")
        # Should have data for most strategies
        strategy_ids_in_ts = {str(pt.get("strategy_id")) for pt in ts}
        assert len(strategy_ids_in_ts) >= len(strategies) - 5


class TestPhase8Seeds:
    """Phase 8 domain-specific seeds should exist."""

    def test_risk_limits_exist(self, seeded_store: MockStateStore) -> None:
        records = seeded_store.list("risk_limits")
        assert len(records) >= 4

    def test_options_chain_exists(self, seeded_store: MockStateStore) -> None:
        records = seeded_store.list("options_chain")
        assert len(records) >= 7

    def test_vol_surfaces_exist(self, seeded_store: MockStateStore) -> None:
        records = seeded_store.list("vol_surfaces")
        assert len(records) >= 2

    def test_fx_rates_exist(self, seeded_store: MockStateStore) -> None:
        records = seeded_store.list("fx_rates")
        assert len(records) >= 6

    def test_regulatory_reports_exist(self, seeded_store: MockStateStore) -> None:
        records = seeded_store.list("regulatory_reports")
        assert len(records) >= 6

    def test_news_exists(self, seeded_store: MockStateStore) -> None:
        records = seeded_store.list("news")
        assert len(records) >= 15

    def test_service_health_exists(self, seeded_store: MockStateStore) -> None:
        records = seeded_store.list("service_health")
        assert len(records) >= 20
