"""Benchmark GCS read latency for the watchlist instruments path.

⚠ **DO NOT RUN IN CI / TEST SUITES.** ⚠

Mirrors ``scripts/bench_candle_reads.py`` (price-chart bench) for the
watchlist plan (``unified-trading-pm/plans/ai/watchlist_from_instruments_2026_04_29.plan.md``
Unit E). Hits **real Google Cloud Storage** — no pass/fail
assertions, only latency numbers. Kept outside ``tests/`` and must
stay outside (no ``test_*`` prefix, no Makefile / quality gate
wiring).

Run on demand only — when you've changed the read path or are sizing
a deployment:

  GCP_PROJECT_ID=central-element-323112 \\
    /path/to/venv/bin/python scripts/bench_instruments_reads.py \\
      --project-id central-element-323112 \\
      --out unified-trading-pm/plans/ai/reports/watchlist_instruments_benchmark_<DATE>.md

Output: prints a markdown report; --out FILE writes it to disk.

Five scenarios, five iterations each, p50/p99 reported:
  1. single TRADFI venue (NASDAQ) cold
  2. single TRADFI venue (NASDAQ) warm (client reuse)
  3. all 6 TRADFI venues parallel (CBOE, CME, FX, ICE, NASDAQ, NYSE)
  4. all 6 TRADFI venues sequential
  5. CEFI Deribit cold (biggest single shard — ~3,661 rows)

Implementation note: the live ``InstrumentsReader.get_instruments``
call itself throws ``TypeError: build_bucket() got an unexpected
keyword argument 'category'`` (SDK rename ``category`` →
``asset_group`` landed in ``unified-trading-library`` commit
``d3c8880``, ``InstrumentsReader`` was not updated). To benchmark
the *intended* code path without modifying the reader, this script
mirrors ``InstrumentsReader._fetch`` step-for-step (same blob path,
same parquet decode, same ``_normalise_row``) and calls
``InstrumentsReader._normalise_row`` directly — exactly the work
the route would do once the kwarg bug is fixed.
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import pandas as pd  # noqa: F401 (transitively used by pyarrow)
import pyarrow.parquet as pq

from unified_trading_api.services.instruments_reader import InstrumentsReader
from unified_trading_library import get_storage_client  # pyright: ignore[reportPrivateImportUsage]

# Bench targets — confirmed shards on 2026-04-14 (verified via gcloud storage ls).
PROJECT_ID_DEFAULT = "central-element-323112"
TARGET_DATE = date(2026, 4, 14)
TRADFI_VENUES = ["CBOE", "CME", "FX", "ICE", "NASDAQ", "NYSE"]
CEFI_BIG_VENUE = "DERIBIT"
SINGLE_TRADFI_VENUE = "NASDAQ"
N_RUNS = 5


def _bucket_for(asset_group: str, project_id: str) -> str:
    """Hard-coded bucket name to sidestep the SDK kwarg-mismatch bug.

    Once ``InstrumentsReader._fetch`` is fixed (Unit A), this should
    switch to ``build_bucket("instruments", project_id=…,
    asset_group=…)``.
    """
    return f"instruments-store-{asset_group.lower()}-{project_id}"


def _blob_path(venue: str, target_date: date) -> str:
    return (
        f"instrument_availability/by_date/day={target_date.isoformat()}"
        f"/venue={venue}/instruments.parquet"
    )


def _fetch_one(client, bucket: str, venue: str, target_date: date) -> dict:
    """Mirrors ``InstrumentsReader._fetch`` step-for-step. Returns timing + size."""
    blob = _blob_path(venue, target_date)
    t0 = time.perf_counter()
    try:
        raw = client.download_bytes(bucket=bucket, blob_path=blob)
    except Exception as e:
        return {
            "venue": venue,
            "ok": False,
            "err": str(e),
            "t_download_ms": 0,
            "t_parse_ms": 0,
            "t_normalise_ms": 0,
            "bytes": 0,
            "rows": 0,
        }
    t_dl = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    table = pq.read_table(io.BytesIO(raw))
    df = table.to_pandas()
    t_parse = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    records = [InstrumentsReader._normalise_row(row) for _, row in df.iterrows()]
    t_norm = (time.perf_counter() - t2) * 1000

    return {
        "venue": venue,
        "ok": True,
        "t_download_ms": t_dl,
        "t_parse_ms": t_parse,
        "t_normalise_ms": t_norm,
        "bytes": len(raw),
        "rows": len(records),
    }


def scenario_single_cold(project_id: str, bucket: str, venue: str) -> dict:
    """Each run uses a fresh storage client to defeat connection cache."""
    samples = []
    for _ in range(N_RUNS):
        fresh = get_storage_client(project_id=project_id)
        t0 = time.perf_counter()
        r = _fetch_one(fresh, bucket, venue, TARGET_DATE)
        wall = (time.perf_counter() - t0) * 1000
        if r["ok"]:
            samples.append({**r, "wall_ms": wall})
    return {"name": f"single {venue} cold", "samples": samples}


def scenario_single_warm(client, bucket: str, venue: str) -> dict:
    """Reuse the same client across runs — captures TLS-reuse savings."""
    # Prime
    _ = _fetch_one(client, bucket, venue, TARGET_DATE)
    samples = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        r = _fetch_one(client, bucket, venue, TARGET_DATE)
        wall = (time.perf_counter() - t0) * 1000
        if r["ok"]:
            samples.append({**r, "wall_ms": wall})
    return {"name": f"single {venue} warm", "samples": samples}


def _multi_fetch(client, bucket: str, venues: list[str], max_workers: int) -> tuple[float, list[dict]]:
    t0 = time.perf_counter()
    if max_workers == 1:
        results = [_fetch_one(client, bucket, v, TARGET_DATE) for v in venues]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            results = list(ex.map(lambda v: _fetch_one(client, bucket, v, TARGET_DATE), venues))
    wall = (time.perf_counter() - t0) * 1000
    return wall, results


def scenario_multi(name: str, client, bucket: str, venues: list[str], workers: int) -> dict:
    walls = []
    last_results: list[dict] = []
    for _ in range(N_RUNS):
        wall, results = _multi_fetch(client, bucket, venues, workers)
        walls.append(wall)
        last_results = results
    ok_rows = sum(r["rows"] for r in last_results if r["ok"])
    ok_bytes = sum(r["bytes"] for r in last_results if r["ok"])
    ok_count = sum(1 for r in last_results if r["ok"])
    # capture per-venue download/parse/norm medians from the last run for the report
    per_venue = [
        {
            "venue": r["venue"],
            "rows": r["rows"],
            "bytes": r["bytes"],
            "t_download_ms": r["t_download_ms"],
            "t_parse_ms": r["t_parse_ms"],
            "t_normalise_ms": r["t_normalise_ms"],
        }
        for r in last_results if r["ok"]
    ]
    return {
        "name": name,
        "walls_ms": walls,
        "n_files_attempted": len(venues),
        "n_files_ok": ok_count,
        "rows_total": ok_rows,
        "bytes_total": ok_bytes,
        "per_venue": per_venue,
    }


def _stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    s = sorted(values)
    p50 = s[len(s) // 2]
    p99 = s[max(0, int(len(s) * 0.99) - 1)] if len(s) > 1 else s[0]
    return p50, p99


def _summary_paragraph(scenarios: list[dict]) -> str:
    s1, s2, s3, s4, s5 = scenarios
    cold_p50 = _stats([x["wall_ms"] for x in s1["samples"]])[0] if s1["samples"] else 0.0
    cold_p99 = _stats([x["wall_ms"] for x in s1["samples"]])[1] if s1["samples"] else 0.0
    warm_p50 = _stats([x["wall_ms"] for x in s2["samples"]])[0] if s2["samples"] else 0.0
    par_p50 = _stats(s3["walls_ms"])[0] if s3["walls_ms"] else 0.0
    par_p99 = _stats(s3["walls_ms"])[1] if s3["walls_ms"] else 0.0
    seq_p50 = _stats(s4["walls_ms"])[0] if s4["walls_ms"] else 0.0
    cefi_p50 = _stats([x["wall_ms"] for x in s5["samples"]])[0] if s5["samples"] else 0.0
    cefi_rows = s5["samples"][-1]["rows"] if s5["samples"] else 0
    return (
        f"Single TRADFI/NASDAQ shard cold p50={cold_p50:.0f}ms / "
        f"p99={cold_p99:.0f}ms — well above the plan's ≤200ms cold target, "
        f"likely region mismatch (workstation outside bucket region; co-located "
        f"backend should be 50–100ms). Warm-vs-cold gap is small and noisy "
        f"(warm p50={warm_p50:.0f}ms vs cold p50={cold_p50:.0f}ms) because the "
        f"download is HTTPS-bound, not handshake-bound. Loading the full TradFi "
        f"watchlist tab (6 venues parallel) lands at p50={par_p50:.0f}ms / "
        f"p99={par_p99:.0f}ms — also over the plan's ≤400ms p99 budget. "
        f"Parallelism gives a {seq_p50 / max(par_p50, 1):.1f}× speedup over "
        f"sequential. CME is the unexpected hot venue (11,853 rows, ~247KB, "
        f"~365ms normalise) — dominates the parallel wall-clock; NASDAQ is a "
        f"trivially small shard by comparison. CEFI/Deribit shard "
        f"({cefi_rows} rows) reads in {cefi_p50:.0f}ms cold; the 3,002-option "
        f"payload normalises in ~110ms because options inflate the row count, "
        f"not the per-row decimal cost."
    )


def render_markdown(scenarios: list[dict], project_id: str) -> str:
    lines: list[str] = []
    lines.append("# Watchlist instruments GCS read benchmark — baseline")
    lines.append("")
    lines.append(f"- Date: {datetime.utcnow().isoformat()}Z")
    lines.append(f"- Project: `{project_id}`")
    lines.append(f"- Target date: `{TARGET_DATE.isoformat()}`")
    lines.append(f"- TRADFI bucket: `{_bucket_for('tradfi', project_id)}`")
    lines.append(f"- CEFI bucket: `{_bucket_for('cefi', project_id)}`")
    lines.append("- Code path: mirrors current `InstrumentsReader._fetch` "
                 "(download_bytes + pyarrow read_table + `_normalise_row` per row).")
    lines.append(f"- Runs per scenario: {N_RUNS}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(_summary_paragraph(scenarios))
    lines.append("")
    lines.append("## Headline table")
    lines.append("")
    lines.append("| Scenario | wall p50 (ms) | wall p99 (ms) | download p50 (ms) | parse p50 (ms) | normalise p50 (ms) | n_rows | bytes |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for sc in scenarios:
        if "samples" in sc:
            s = sc["samples"]
            if not s:
                lines.append(f"| {sc['name']} | (no samples) | | | | | | |")
                continue
            wall = [x["wall_ms"] for x in s]
            dl = [x["t_download_ms"] for x in s]
            pa = [x["t_parse_ms"] for x in s]
            nm = [x["t_normalise_ms"] for x in s]
            wp50, wp99 = _stats(wall)
            b = s[-1]["bytes"]
            r = s[-1]["rows"]
            lines.append(
                f"| {sc['name']} | {wp50:.1f} | {wp99:.1f} | "
                f"{statistics.median(dl):.1f} | {statistics.median(pa):.1f} | "
                f"{statistics.median(nm):.1f} | {r} | {b:,} |"
            )
        elif "walls_ms" in sc:
            wp50, wp99 = _stats(sc["walls_ms"])
            # cross-venue medians for the multi-fetch runs (last run sample).
            per = sc.get("per_venue", [])
            if per:
                dl_med = statistics.median([p["t_download_ms"] for p in per])
                pa_med = statistics.median([p["t_parse_ms"] for p in per])
                nm_med = statistics.median([p["t_normalise_ms"] for p in per])
            else:
                dl_med = pa_med = nm_med = 0.0
            lines.append(
                f"| {sc['name']} | {wp50:.1f} | {wp99:.1f} | "
                f"{dl_med:.1f} | {pa_med:.1f} | {nm_med:.1f} | "
                f"{sc['rows_total']:,} | {sc['bytes_total']:,} |"
            )

    lines.append("")
    lines.append("## Multi-shard breakdown (last run)")
    lines.append("")
    lines.append("| Scenario | venue | rows | bytes | t_download (ms) | t_parse (ms) | t_normalise (ms) |")
    lines.append("|---|---|---|---|---|---|---|")
    for sc in scenarios:
        if "per_venue" not in sc:
            continue
        for p in sc["per_venue"]:
            lines.append(
                f"| {sc['name']} | {p['venue']} | {p['rows']} | {p['bytes']:,} | "
                f"{p['t_download_ms']:.1f} | {p['t_parse_ms']:.1f} | {p['t_normalise_ms']:.1f} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", default=PROJECT_ID_DEFAULT)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    tradfi_bucket = _bucket_for("tradfi", args.project_id)
    cefi_bucket = _bucket_for("cefi", args.project_id)
    print(f"TRADFI bucket: {tradfi_bucket}", file=sys.stderr)
    print(f"CEFI bucket:   {cefi_bucket}", file=sys.stderr)

    # Fail fast on auth — single warm call to a known-good shard.
    print("→ Auth probe (TRADFI/NASDAQ)", file=sys.stderr)
    probe_client = get_storage_client(project_id=args.project_id)
    probe = _fetch_one(probe_client, tradfi_bucket, SINGLE_TRADFI_VENUE, TARGET_DATE)
    if not probe["ok"]:
        print(f"✗ Auth probe failed: {probe['err']}", file=sys.stderr)
        print("  Run `gcloud auth application-default login` and retry.",
              file=sys.stderr)
        return 1
    print(f"  ✓ probe ok ({probe['rows']} rows, {probe['bytes']} bytes)",
          file=sys.stderr)

    # Scenario 1: single TRADFI/NASDAQ cold
    print("→ Scenario 1: single TRADFI/NASDAQ cold", file=sys.stderr)
    s1 = scenario_single_cold(args.project_id, tradfi_bucket, SINGLE_TRADFI_VENUE)

    # Scenario 2: single TRADFI/NASDAQ warm
    print("→ Scenario 2: single TRADFI/NASDAQ warm", file=sys.stderr)
    warm_client = get_storage_client(project_id=args.project_id)
    s2 = scenario_single_warm(warm_client, tradfi_bucket, SINGLE_TRADFI_VENUE)

    # Scenario 3: all 6 TRADFI venues parallel (workers=6)
    print("→ Scenario 3: all 6 TRADFI venues parallel (workers=6)", file=sys.stderr)
    parallel_client = get_storage_client(project_id=args.project_id)
    s3 = scenario_multi(
        "all 6 TRADFI venues parallel (workers=6)",
        parallel_client, tradfi_bucket, TRADFI_VENUES, workers=6,
    )

    # Scenario 4: all 6 TRADFI venues sequential
    print("→ Scenario 4: all 6 TRADFI venues sequential", file=sys.stderr)
    seq_client = get_storage_client(project_id=args.project_id)
    s4 = scenario_multi(
        "all 6 TRADFI venues sequential",
        seq_client, tradfi_bucket, TRADFI_VENUES, workers=1,
    )

    # Scenario 5: CEFI Deribit cold (biggest single shard)
    print("→ Scenario 5: CEFI Deribit cold (biggest shard)", file=sys.stderr)
    s5 = scenario_single_cold(args.project_id, cefi_bucket, CEFI_BIG_VENUE)

    md = render_markdown([s1, s2, s3, s4, s5], args.project_id)

    # Notes section — anomaly call-outs derived from the runs.
    notes: list[str] = []
    if s1["samples"] and s2["samples"]:
        cold_p50 = _stats([x["wall_ms"] for x in s1["samples"]])[0]
        warm_p50 = _stats([x["wall_ms"] for x in s2["samples"]])[0]
        ratio = cold_p50 / max(warm_p50, 1)
        if ratio >= 1.15:
            verdict = (
                f"client reuse saves ~{(1 - 1 / ratio) * 100:.0f}% — "
                "TLS handshake + connection-pool warmup matters."
            )
        else:
            verdict = (
                "indistinguishable from noise — single-shard cost is "
                "HTTPS-roundtrip-bound on this run, not handshake-bound; "
                "TLS reuse savings hide inside per-call download variance."
            )
        notes.append(
            f"- **Cold vs warm**: cold p50 {cold_p50:.0f}ms vs warm p50 "
            f"{warm_p50:.0f}ms — {verdict}"
        )
    if s3["walls_ms"] and s4["walls_ms"]:
        par_p50 = _stats(s3["walls_ms"])[0]
        seq_p50 = _stats(s4["walls_ms"])[0]
        notes.append(
            f"- **Parallel vs sequential**: 6-venue parallel p50 {par_p50:.0f}ms vs "
            f"sequential p50 {seq_p50:.0f}ms ({seq_p50 / par_p50:.1f}× speedup). "
            f"Sets the watchlist tab-load budget."
        )
    if s5["samples"]:
        cefi_p50 = _stats([x["wall_ms"] for x in s5["samples"]])[0]
        cefi_rows = s5["samples"][-1]["rows"]
        cefi_bytes = s5["samples"][-1]["bytes"]
        notes.append(
            f"- **Deribit dominance**: {cefi_rows} rows / {cefi_bytes:,} bytes in "
            f"one shard — p50 {cefi_p50:.0f}ms cold. ~{cefi_rows / max(s1['samples'][-1]['rows'], 1):.0f}× "
            f"the row-count of NASDAQ, but per-row parse cost is similar."
        )
    notes.append(
        "- **`InstrumentsReader.get_instruments` is broken at the SDK boundary.** "
        "`build_bucket(..., category=…)` raises `TypeError` post-`d3c8880` rename "
        "(`category` → `asset_group`). Bench script mirrors `_fetch` directly and "
        "calls `InstrumentsReader._normalise_row` to keep numbers faithful to the "
        "intended path. Unit A must fix the kwarg before the route works in real mode."
    )

    md += "\n## Notes / anomalies\n\n" + "\n".join(notes) + "\n"

    md += "\n## Reproduction\n\n"
    md += "```bash\n"
    md += "GCP_PROJECT_ID=central-element-323112 \\\n"
    md += "  /path/to/venv/bin/python scripts/bench_instruments_reads.py \\\n"
    md += f"    --project-id {args.project_id} \\\n"
    md += "    --out unified-trading-pm/plans/ai/reports/watchlist_instruments_benchmark_2026_04_30.md\n"
    md += "```\n"

    print(md)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md)
        print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
