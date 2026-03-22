"""Tests verifying seed data quality and referential integrity."""

from __future__ import annotations

import pytest

from unified_trading_api.mock_data.personas import ORG_IDS, ORGANIZATIONS, PERSONAS


class _InMemoryStore:
    """Minimal in-memory store for seed testing."""

    def __init__(self) -> None:
        self._data: dict[str, list[dict[str, object]]] = {}

    def seed(self, domain: str, records: list[dict[str, object]]) -> None:
        self._data[domain] = list(records)

    def list(self, domain: str) -> list[dict[str, object]]:
        return list(self._data.get(domain, []))


@pytest.fixture(scope="module")
def store() -> _InMemoryStore:
    s = _InMemoryStore()
    from unified_trading_api.mock_data.seed import seed_all_domains

    seed_all_domains(s)
    return s


class TestOrgIdCoverage:
    """Every record in every domain must have an org_id field."""

    DOMAINS_REQUIRING_ORG = [
        "orders",
        "fills",
        "positions",
        "strategies",
        "alerts",
        "risk_limits",
        "model_families",
        "experiments",
    ]

    @pytest.mark.parametrize("domain", DOMAINS_REQUIRING_ORG)
    def test_all_records_have_org_id(self, store: _InMemoryStore, domain: str) -> None:
        records = store.list(domain)
        assert len(records) > 0, f"Domain '{domain}' has no records"
        for i, record in enumerate(records):
            assert "org_id" in record, f"Record {i} in '{domain}' missing org_id"


class TestReferentialIntegrity:
    """Cross-domain references must be valid."""

    def test_fill_order_ids_reference_valid_orders(self, store: _InMemoryStore) -> None:
        order_ids = {str(o["order_id"]) for o in store.list("orders")}
        fills = store.list("fills")
        for fill in fills:
            oid = str(fill.get("order_id", ""))
            if oid:
                assert oid in order_ids, f"Fill references unknown order_id: {oid}"

    def test_position_strategy_ids_reference_valid_strategies(self, store: _InMemoryStore) -> None:
        strategy_ids = {str(s["id"]) for s in store.list("strategies")}
        positions = store.list("positions")
        for pos in positions:
            sid = str(pos.get("strategy_id", ""))
            if sid:
                assert sid in strategy_ids, f"Position references unknown strategy_id: {sid}"

    def test_org_ids_are_valid(self, store: _InMemoryStore) -> None:
        valid_orgs = set(ORG_IDS)
        for domain in ["orders", "positions", "strategies"]:
            for record in store.list(domain):
                oid = str(record.get("org_id", ""))
                assert oid in valid_orgs, f"Invalid org_id '{oid}' in {domain}"


class TestRecordCounts:
    """Verify minimum record counts per domain."""

    def test_strategies_count(self, store: _InMemoryStore) -> None:
        assert len(store.list("strategies")) >= 18

    def test_positions_count(self, store: _InMemoryStore) -> None:
        assert len(store.list("positions")) >= 15

    def test_orders_count(self, store: _InMemoryStore) -> None:
        assert len(store.list("orders")) >= 20

    def test_fills_count(self, store: _InMemoryStore) -> None:
        assert len(store.list("fills")) >= 30

    def test_alerts_count(self, store: _InMemoryStore) -> None:
        assert len(store.list("alerts")) >= 15

    def test_service_health_count(self, store: _InMemoryStore) -> None:
        assert len(store.list("service_health")) >= 21


class TestBatchLiveSeparation:
    """Batch and live domains must both exist and differ."""

    def test_positions_batch_and_live_exist(self, store: _InMemoryStore) -> None:
        batch = store.list("positions_batch")
        live = store.list("positions_live")
        assert len(batch) > 0
        assert len(live) > 0

    def test_pnl_batch_and_live_exist(self, store: _InMemoryStore) -> None:
        batch = store.list("pnl_batch")
        live = store.list("pnl_live")
        assert len(batch) > 0
        assert len(live) > 0


class TestAlertSeverityDistribution:
    """Alerts must have realistic severity distribution."""

    def test_severity_distribution(self, store: _InMemoryStore) -> None:
        alerts = store.list("alerts")
        severities = [str(a.get("severity", "")) for a in alerts]
        assert "critical" in severities or "CRITICAL" in severities
        assert "high" in severities or "HIGH" in severities
        assert "medium" in severities or "MEDIUM" in severities
        assert "low" in severities or "LOW" in severities


class TestPersonaSSOT:
    """Persona definitions are correct."""

    def test_four_orgs(self) -> None:
        assert len(ORGANIZATIONS) == 4

    def test_five_personas(self) -> None:
        assert len(PERSONAS) == 5

    def test_persona_org_ids_valid(self) -> None:
        valid_orgs = set(ORG_IDS)
        for persona in PERSONAS:
            assert str(persona["org_id"]) in valid_orgs
