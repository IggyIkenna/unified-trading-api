"""Schema-parity tests for /instruments/live-universe.

Two sources of truth, both asserted:

1. *.sample.json fixtures captured from a real backend boot reading GCS.
   These are the **canonical real-world shape** at capture time. When real
   GCS schema changes, regen → diff is loud → every test that asserts shape
   lights up.

2. UAC ``InstrumentRecord`` Pydantic model. The **authoritative contract**
   the platform's supposed to obey. Catches drift in either direction:
   - GCS starts emitting a new field UAC doesn't know about → validation fails.
   - UAC adds a required field GCS doesn't yet emit → validation fails.

Tests don't hit GCS. They run against the captured fixtures and the
backend route's mock-mode response (in-memory MockStateStore). The
real-mode round-trip is asserted by ``scripts/check_live_universe_schema.py``,
run manually / on a weekly cron, NOT in CI.

Pattern: `unified-trading-pm/codex/06-coding-standards/ui-testing-layers.md` (L1.5)
Plan: `unified-trading-pm/plans/ai/watchlist_from_instruments_2026_04_29.plan.md` Unit B
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from unified_api_contracts.internal.reference.instrument import (  # noqa: qg-deep-import — UAC internal facade
    InstrumentRecord,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "live-universe"
ASSET_GROUPS = ("cefi", "tradfi", "defi")


# DeFi rows carry on-chain provenance fields that aren't in the canonical
# InstrumentRecord — they live as adapter-specific extras (pool_address,
# *_contract_address, *_decimals, *_symbol_onchain, atoken_address,
# debt_token_address, pool_fee_tier). Allowed in fixtures, ignored by UAC.
DEFI_EXTRAS_ALLOWED = {
    "pool_address",
    "pool_fee_tier",
    "atoken_address",
    "debt_token_address",
    "base_asset_contract_address",
    "quote_asset_contract_address",
    "base_asset_decimals",
    "quote_asset_decimals",
    "base_asset_symbol_onchain",
    "quote_asset_symbol_onchain",
}


# ---------------------------------------------------------------------------
# Source 1 — sample fixtures vs themselves (sanity)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("asset_group", ASSET_GROUPS)
def test_fixture_loads_and_has_data(asset_group: str) -> None:
    """Each fixture loads, has the documented shape, and is non-empty."""
    payload = json.loads((FIXTURES / f"{asset_group}.sample.json").read_text())
    assert payload["asset_group"] == asset_group
    assert "data" in payload
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) > 0, "fixture has no rows — regen needed"


# ---------------------------------------------------------------------------
# Source 2 — fixture rows validate against UAC InstrumentRecord
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("asset_group", ASSET_GROUPS)
def test_fixture_rows_validate_against_uac_instrument_record(asset_group: str) -> None:
    """Every row in the fixture must validate against UAC InstrumentRecord.

    This is the DRIFT DETECTOR. If real GCS starts emitting a field UAC
    doesn't know about, Pydantic raises ValidationError on that row.
    If UAC adds a required field GCS doesn't yet emit, same result.

    Pydantic's default `extra='ignore'` means *unknown* fields don't fail
    validation by themselves — but we explicitly pass `extra='forbid'`
    here so we DO catch unknown fields (the whole point).

    DeFi rows carry on-chain provenance extras (pool_address, *_decimals,
    etc.) that aren't in UAC. We strip the documented set before validation
    so the test catches *NEW* unknown fields, not the known-and-allowed
    ones. The column-set test below is the canary for "a new extra
    appeared that nobody told us about."
    """
    payload = json.loads((FIXTURES / f"{asset_group}.sample.json").read_text())

    # Tighten validation to forbid unknown fields. We want loud failure
    # when GCS adds a column UAC hasn't modeled yet.
    class StrictInstrumentRecord(InstrumentRecord):
        model_config = {**InstrumentRecord.model_config, "extra": "forbid"}

    failures: list[tuple[int, str]] = []
    for idx, row in enumerate(payload["data"]):
        # For DeFi: strip the documented adapter-specific extras before
        # UAC validation. The column-set test below catches NEW unknown
        # extras; this test catches drift in *modeled* fields.
        cleaned = (
            {k: v for k, v in row.items() if k not in DEFI_EXTRAS_ALLOWED}
            if asset_group == "defi"
            else row
        )
        try:
            StrictInstrumentRecord.model_validate(cleaned)
        except ValidationError as exc:
            failures.append((idx, str(exc)))

    if failures:
        msg = (
            f"{asset_group}: {len(failures)}/{len(payload['data'])} rows failed UAC validation.\n"
            f"First 3 failures:\n"
            + "\n---\n".join(f"  row {idx}: {err}" for idx, err in failures[:3])
            + "\n\nDrift detected — either GCS schema changed (regen the fixture) "
            "or UAC added a field GCS doesn't emit (file an instruments-service issue)."
        )
        pytest.fail(msg)


# ---------------------------------------------------------------------------
# Cross-check — fixture column set matches UAC field set (modulo on-chain extras)
# ---------------------------------------------------------------------------


def _uac_fields() -> set[str]:
    return set(InstrumentRecord.model_fields.keys())


@pytest.mark.parametrize("asset_group", ASSET_GROUPS)
def test_fixture_columns_subset_of_uac_or_known_defi_extras(asset_group: str) -> None:
    """Every fixture column is either in UAC InstrumentRecord, or is a
    known DeFi-only on-chain extra.

    Catches the case where a NEW unknown column appears that's neither
    in UAC nor in our explicit DEFI_EXTRAS_ALLOWED list — that means
    something changed upstream and a human needs to decide which bucket
    it belongs in.
    """
    payload = json.loads((FIXTURES / f"{asset_group}.sample.json").read_text())
    fixture_cols: set[str] = set()
    for row in payload["data"]:
        fixture_cols.update(row.keys())

    allowed = _uac_fields()
    if asset_group == "defi":
        allowed = allowed | DEFI_EXTRAS_ALLOWED

    unknown = fixture_cols - allowed
    if unknown:
        pytest.fail(
            f"{asset_group}: fixture has columns not in UAC and not in known extras: "
            f"{sorted(unknown)}.\n"
            "Either: (a) UAC needs to be extended; or "
            "(b) DEFI_EXTRAS_ALLOWED in this test needs the new column."
        )


# ---------------------------------------------------------------------------
# Source 3 — backend mock-mode response shape matches the fixtures
# ---------------------------------------------------------------------------
# In mock mode the route returns whatever the seed store has for
# "instruments". We don't assert exact rows — the seed shape is its
# own concern. We DO assert the response envelope is the same shape
# as a real-mode response (fixture reference).


def test_mock_mode_response_envelope_matches_fixture_shape(app_client: TestClient) -> None:
    """Mock-mode response wraps `data` the same way the real route does.

    Asserts the envelope keys (`data`, `asset_group`, optionally `as_of`,
    `total`). Doesn't assert row content — mock seed is allowed to lag
    behind real GCS.
    """
    resp = app_client.get("/instruments/live-universe?asset_group=cefi")
    assert resp.status_code == 200
    body = resp.json()

    assert "data" in body, "envelope missing `data` key"
    assert isinstance(body["data"], list)

    # Fixture envelope keys — at minimum, we expect the same shape.
    fixture = json.loads((FIXTURES / "cefi.sample.json").read_text())
    fixture_envelope_keys = set(fixture.keys()) - {"data"}
    response_envelope_keys = set(body.keys()) - {"data"}

    # Fixture must be a SUBSET of response keys (response can carry extras
    # like a `meta` block, but it can't drop fields the fixture has).
    missing = fixture_envelope_keys - response_envelope_keys
    if missing:
        pytest.fail(
            f"mock-mode response missing envelope keys present in fixture: {sorted(missing)}.\n"
            "If the fixture has fields the route doesn't emit, either the route is wrong "
            "or the fixture was captured against a different code version."
        )


def test_mock_mode_400_on_missing_asset_group(app_client: TestClient) -> None:
    """Bad request: asset_group is required."""
    resp = app_client.get("/instruments/live-universe")
    # FastAPI's default for missing required Query is 422
    assert resp.status_code == 422


def test_mock_mode_response_shape_for_each_asset_group(app_client: TestClient) -> None:
    """All three asset groups return a valid envelope in mock mode."""
    for ag in ASSET_GROUPS:
        resp = app_client.get(f"/instruments/live-universe?asset_group={ag}")
        assert resp.status_code == 200, f"{ag}: {resp.status_code}"
        body = resp.json()
        assert "data" in body and isinstance(body["data"], list), f"{ag}: bad envelope"
