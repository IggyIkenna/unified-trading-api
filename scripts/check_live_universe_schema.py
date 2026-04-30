"""Schema-drift detector for /instruments/live-universe.

Hits the running backend (real mode → real GCS), captures the response,
and diffs it against:
1. The captured *.sample.json fixtures (in either repo).
2. The UAC InstrumentRecord Pydantic model.

Exits non-zero on drift, with a human-readable diff. Run manually
before a release or on a weekly cron — NOT on every pytest run
(those are fixture-only and already cover the same parity assertions).

Usage
-----
    # against a running backend on :8030
    python scripts/check_live_universe_schema.py

    # explicit URL / specific asset groups
    python scripts/check_live_universe_schema.py \\
        --url http://localhost:8030 \\
        --asset-groups cefi tradfi

    # write a markdown report
    python scripts/check_live_universe_schema.py \\
        --report unified-trading-pm/plans/ai/reports/live_universe_schema_drift_$(date +%Y_%m_%d).md

What it catches
---------------
- A field appearing in real GCS that's not in UAC → loud, with the
  field name. Action: extend UAC InstrumentRecord (or add to
  DEFI_EXTRAS_ALLOWED if it's an adapter-specific extra).
- A UAC required field that real GCS doesn't emit → loud. Action:
  fix the upstream writer or relax the field on UAC.
- Real response missing the canonical envelope keys (`data`,
  `asset_group`, `total`) → loud. Action: fix the route.
- Real response shape diverges from the captured fixtures → loud.
  Action: regen the fixtures.

Plan: unified-trading-pm/plans/ai/watchlist_from_instruments_2026_04_29.plan.md Unit F
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# UAC InstrumentRecord — authoritative contract.
from unified_api_contracts.internal.reference.instrument import (  # noqa: qg-deep-import — UAC
    InstrumentRecord,
)
from pydantic import ValidationError


# Adapter-specific extras that DeFi rows carry but UAC doesn't model.
# Mirror of tests/unit/test_live_universe_schema.py:DEFI_EXTRAS_ALLOWED.
DEFI_EXTRAS_ALLOWED: frozenset[str] = frozenset(
    {
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
)

DEFAULT_FIXTURES_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "live-universe"


# ---------------------------------------------------------------------------
# Drift kinds — each finding is one of these.
# ---------------------------------------------------------------------------


def _uac_field_set() -> frozenset[str]:
    return frozenset(InstrumentRecord.model_fields.keys())


def _fetch_live_universe(base_url: str, asset_group: str, timeout: float = 60.0) -> dict:
    url = f"{base_url.rstrip('/')}/instruments/live-universe?asset_group={asset_group}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — internal URL
        return json.loads(resp.read().decode("utf-8"))


def _columns_in(rows: list[dict]) -> set[str]:
    cols: set[str] = set()
    for row in rows:
        cols.update(row.keys())
    return cols


def _strict_validate_row(row: dict, asset_group: str) -> str | None:
    """Validate one row against UAC InstrumentRecord with extra='forbid'.

    Returns None on pass, error message on failure. Strips DEFI_EXTRAS_ALLOWED
    for DeFi rows (they're modeled as adapter extras, not UAC fields).
    """

    class StrictInstrumentRecord(InstrumentRecord):
        model_config = {**InstrumentRecord.model_config, "extra": "forbid"}

    cleaned = (
        {k: v for k, v in row.items() if k not in DEFI_EXTRAS_ALLOWED}
        if asset_group == "defi"
        else row
    )
    try:
        StrictInstrumentRecord.model_validate(cleaned)
        return None
    except ValidationError as exc:
        return str(exc)


# ---------------------------------------------------------------------------
# Per-asset-group drift report
# ---------------------------------------------------------------------------


def _check_asset_group(
    asset_group: str,
    real_response: dict,
    fixture_response: dict | None,
) -> list[str]:
    """Return a list of drift findings for this asset group. Empty = clean."""
    findings: list[str] = []

    # Envelope shape
    if "data" not in real_response or not isinstance(real_response.get("data"), list):
        findings.append(f"[envelope] real response missing or non-list `data`")
    if real_response.get("asset_group") != asset_group:
        findings.append(
            f"[envelope] real response asset_group={real_response.get('asset_group')!r} != requested {asset_group!r}"
        )
    if "total" not in real_response:
        findings.append("[envelope] real response missing `total`")

    rows = real_response.get("data", [])
    if not rows:
        findings.append("[content] real response has zero rows — backend may be misconfigured")
        return findings

    real_cols = _columns_in(rows)
    uac_fields = _uac_field_set()
    allowed = uac_fields | (DEFI_EXTRAS_ALLOWED if asset_group == "defi" else frozenset())

    # Unknown columns — neither in UAC nor in known extras
    unknown = real_cols - allowed
    if unknown:
        findings.append(
            f"[columns] real response has unknown columns not in UAC and not in DEFI_EXTRAS_ALLOWED: {sorted(unknown)}\n"
            f"  → either UAC needs to be extended OR add to DEFI_EXTRAS_ALLOWED in this script + the matching test"
        )

    # UAC fields missing from real response — usually OK (most fields are
    # optional), but flag any that are explicitly required by UAC and
    # never present.
    required_uac_fields = {
        name for name, info in InstrumentRecord.model_fields.items() if info.is_required()
    }
    always_missing = required_uac_fields - real_cols
    if always_missing:
        findings.append(
            f"[columns] real response is missing UAC-required columns: {sorted(always_missing)}"
        )

    # Strict per-row UAC validation — catches type drift on existing fields
    row_failures: list[tuple[int, str]] = []
    for idx, row in enumerate(rows):
        err = _strict_validate_row(row, asset_group)
        if err:
            row_failures.append((idx, err))
    if row_failures:
        sample = "\n".join(
            f"  row {idx}: {err.splitlines()[0]}"
            for idx, err in row_failures[:3]
        )
        findings.append(
            f"[content] {len(row_failures)}/{len(rows)} rows failed UAC validation. First 3:\n{sample}"
        )

    # Compare against fixture (if provided)
    if fixture_response is not None:
        fixture_rows = fixture_response.get("data", [])
        fixture_cols = _columns_in(fixture_rows)
        new_in_real = real_cols - fixture_cols
        gone_from_real = fixture_cols - real_cols
        if new_in_real:
            findings.append(
                f"[fixture] real response has columns not in fixture: {sorted(new_in_real)}\n"
                f"  → regen the fixture (see lib/mocks/fixtures/live-universe/README.md)"
            )
        if gone_from_real:
            findings.append(
                f"[fixture] fixture has columns not in real response: {sorted(gone_from_real)}\n"
                f"  → either the route stopped emitting them OR the fixture is from a newer backend version"
            )

    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--url", default="http://localhost:8030", help="Backend base URL")
    parser.add_argument(
        "--asset-groups",
        nargs="+",
        default=["cefi", "tradfi", "defi"],
        choices=["cefi", "tradfi", "defi"],
        help="Asset groups to check (default: all 3)",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_PATH,
        help="Directory containing *.sample.json fixtures (default: tests/fixtures/live-universe)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional markdown report path. If set, writes a summary to disk.",
    )
    args = parser.parse_args(argv)

    print(f"[check] backend = {args.url}")
    print(f"[check] asset groups = {args.asset_groups}")
    print(f"[check] fixtures dir = {args.fixtures_dir}")
    print()

    all_findings: dict[str, list[str]] = {}
    for ag in args.asset_groups:
        print(f"--- {ag} ---")
        try:
            real = _fetch_live_universe(args.url, ag)
        except urllib.error.URLError as exc:
            print(f"  ERROR fetching real backend: {exc}")
            all_findings[ag] = [f"[fetch] failed: {exc}"]
            continue

        fixture = None
        fixture_path = args.fixtures_dir / f"{ag}.sample.json"
        if fixture_path.exists():
            fixture = json.loads(fixture_path.read_text())
        else:
            print(f"  (no fixture at {fixture_path}, skipping fixture diff)")

        findings = _check_asset_group(ag, real, fixture)
        all_findings[ag] = findings
        if findings:
            print(f"  ✗ {len(findings)} drift finding(s):")
            for f in findings:
                print(f"    - {f}")
        else:
            print(f"  ✓ clean ({len(real.get('data', []))} rows)")
        print()

    total_drift = sum(len(v) for v in all_findings.values())
    print(f"\n=== summary ===")
    print(f"  total drift findings: {total_drift}")
    for ag, findings in all_findings.items():
        print(f"  {ag}: {len(findings)}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Live-universe schema drift report",
            "",
            f"- Generated: {datetime.now(UTC).isoformat()}",
            f"- Backend: `{args.url}`",
            f"- Fixtures: `{args.fixtures_dir}`",
            f"- Total findings: {total_drift}",
            "",
        ]
        for ag, findings in all_findings.items():
            lines.append(f"## {ag}")
            lines.append("")
            if not findings:
                lines.append("Clean — no drift detected.")
            else:
                for f in findings:
                    lines.append(f"- {f}")
            lines.append("")
        args.report.write_text("\n".join(lines))
        print(f"\n[report] {args.report}")

    return 1 if total_drift > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
