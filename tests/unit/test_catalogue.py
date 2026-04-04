"""Tests for the permission catalogue API routes and data integrity."""

from __future__ import annotations

from fastapi.testclient import TestClient

from unified_trading_api.models.permission_catalogue import PermissionDomain
from unified_trading_api.models.permission_catalogue_data import PERMISSION_CATALOGUE


class TestCatalogueData:
    """Validate the catalogue data structure itself."""

    def test_all_eight_domains_present(self) -> None:
        domain_values = {d.domain for d in PERMISSION_CATALOGUE.domains}
        expected = set(PermissionDomain)
        assert domain_values == expected, f"Missing domains: {expected - domain_values}"

    def test_total_permissions_positive(self) -> None:
        assert PERMISSION_CATALOGUE.total_permissions > 0

    def test_total_categories_positive(self) -> None:
        assert PERMISSION_CATALOGUE.total_categories > 0

    def test_every_domain_has_categories(self) -> None:
        for domain_node in PERMISSION_CATALOGUE.domains:
            assert len(domain_node.categories) > 0, f"Domain {domain_node.domain} has no categories"

    def test_every_category_has_permissions(self) -> None:
        for domain_node in PERMISSION_CATALOGUE.domains:
            for cat in domain_node.categories:
                assert len(cat.permissions) > 0, (
                    f"Category {cat.key} in {domain_node.domain} has no permissions"
                )

    def test_permission_keys_unique(self) -> None:
        keys: list[str] = []
        for domain_node in PERMISSION_CATALOGUE.domains:
            for cat in domain_node.categories:
                for perm in cat.permissions:
                    keys.append(perm.key)
        assert len(keys) == len(set(keys)), "Duplicate permission keys found"

    def test_internal_only_flags_on_provisioning(self) -> None:
        """All internal provisioning permissions should be flagged internal-only."""
        for domain_node in PERMISSION_CATALOGUE.domains:
            if domain_node.domain == PermissionDomain.INTERNAL_PROVISIONING:
                for cat in domain_node.categories:
                    for perm in cat.permissions:
                        assert perm.is_internal_only, (
                            f"Provisioning perm {perm.key} should be internal-only"
                        )

    def test_platform_internal_perms_flagged(self) -> None:
        """Platform internal tools should be flagged internal-only."""
        for domain_node in PERMISSION_CATALOGUE.domains:
            if domain_node.domain == PermissionDomain.PLATFORM_SERVICES:
                for cat in domain_node.categories:
                    if cat.key == "internal":
                        for perm in cat.permissions:
                            assert perm.is_internal_only, (
                                f"Platform internal perm {perm.key} should be internal-only"
                            )

    def test_entitlement_perms_sourced_from_uac(self) -> None:
        """Feature subscriptions entitlements should match UAC Entitlement enum count."""
        from unified_api_contracts.internal.schemas.rbac import Entitlement

        entitlement_count = len(Entitlement)
        for domain_node in PERMISSION_CATALOGUE.domains:
            if domain_node.domain == PermissionDomain.FEATURE_SUBSCRIPTIONS:
                for cat in domain_node.categories:
                    if cat.key == "entitlements":
                        assert len(cat.permissions) == entitlement_count


class TestCatalogueRoutes:
    """Test the catalogue API endpoints."""

    def test_get_full_catalogue(self, app_client: TestClient) -> None:
        resp = app_client.get("/catalogue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "catalogue"
        assert "data" in data
        assert len(data["data"]["domains"]) == 8

    def test_list_domains(self, app_client: TestClient) -> None:
        resp = app_client.get("/catalogue/domains")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 8
        for domain_summary in data["data"]:
            assert "domain" in domain_summary
            assert "label" in domain_summary
            assert "permission_count" in domain_summary
            assert domain_summary["permission_count"] > 0

    def test_get_single_domain(self, app_client: TestClient) -> None:
        resp = app_client.get("/catalogue/domain/execution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["domain"] == "execution"
        assert len(data["data"]["categories"]) > 0

    def test_get_domain_not_found(self, app_client: TestClient) -> None:
        resp = app_client.get("/catalogue/domain/nonexistent")
        assert resp.status_code == 404

    def test_search_permissions_found(self, app_client: TestClient) -> None:
        resp = app_client.get("/catalogue/search?q=binance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        assert data["query"] == "binance"
        assert len(data["data"]) > 0

    def test_search_permissions_case_insensitive(self, app_client: TestClient) -> None:
        resp_lower = app_client.get("/catalogue/search?q=twap")
        resp_upper = app_client.get("/catalogue/search?q=TWAP")
        assert resp_lower.json()["count"] == resp_upper.json()["count"]
        assert resp_lower.json()["count"] > 0

    def test_search_permissions_no_results(self, app_client: TestClient) -> None:
        resp = app_client.get("/catalogue/search?q=xyznonexistent123")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_search_requires_query(self, app_client: TestClient) -> None:
        resp = app_client.get("/catalogue/search")
        assert resp.status_code == 422  # validation error — q is required

    def test_all_domains_accessible_individually(self, app_client: TestClient) -> None:
        for domain in PermissionDomain:
            resp = app_client.get(f"/catalogue/domain/{domain.value}")
            assert resp.status_code == 200, f"Failed for domain {domain.value}"
