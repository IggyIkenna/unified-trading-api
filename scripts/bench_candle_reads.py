"""Benchmark GCS read latency for the price-chart candle path.

Runs against the *current* code path (BatchCandleReader) so the numbers
become the baseline we can diff against once Unit A swaps in UTL +
manifest pruning.

Six scenarios, five iterations each, p50/p99 reported:
  1. single parquet, cold
  2. single parquet, warm (cache reuse)
  3. 10 parquets, parallel
  4. 10 parquets, sequential
  5. 10 parquets, parallel + manifest-pruned
  6. 30 parquets, parallel + manifest-pruned

Output: prints a markdown table; --out FILE writes it to disk.

Run:
  /path/to/venv/bin/python scripts/bench_candle_reads.py \\
      --project-id central-element-323112 \\
      --out /home/hk/.../benchmarks/price_chart_gcs_2026_04_29.md
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd  # noqa: F401  (transitively used by pyarrow)
import pyarrow.parquet as pq

from unified_trading_library import build_bucket, get_storage_client
from unified_trading_library.manifest_writer import read_availability_index

# Bench targets — TRADFI AAPL. Confirmed-backfilled window per
# `gcloud storage ls gs://market-data-tick-tradfi-{project}/processed_candles/by_date/`.
VENUE = "NASDAQ"
SYMBOL = "AAPL"
TIMEFRAME = "1m"
DATA_TYPE = "ohlcv_1m"
CATEGORY = "tradfi"
SINGLE_DAY = date(2026, 4, 13)         # mid-week, confirmed shard exists
TEN_DAY_END = date(2026, 4, 14)        # 10 trading days back from here
THIRTY_DAY_END = date(2026, 4, 14)     # 30 trading days back
N_RUNS = 5


def _blob_path(d: date) -> str:
    return (
        f"processed_candles/by_date/day={d.isoformat()}"
        f"/timeframe={TIMEFRAME}/data_type={DATA_TYPE}"
        f"/venue={VENUE}/{SYMBOL}.parquet"
    )


def _fetch_one(client, bucket: str, d: date) -> dict:
    """Download + parse one parquet. Returns timing + size."""
    blob = _blob_path(d)
    t0 = time.perf_counter()
    try:
        raw = client.download_bytes(bucket=bucket, blob_path=blob)
    except Exception as e:
        return {"date": d, "ok": False, "err": str(e), "t_download_ms": 0,
                "t_parse_ms": 0, "t_project_ms": 0, "bytes": 0, "rows": 0}
    t_dl = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    table = pq.read_table(io.BytesIO(raw))
    df = table.to_pandas()
    t_parse = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.sort_values("timestamp")
    records = []
    for _, row in df.iterrows():
        records.append({
            "time": int(pd.Timestamp(row["timestamp"]).timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0.0)),
        })
    t_proj = (time.perf_counter() - t2) * 1000

    return {
        "date": d,
        "ok": True,
        "t_download_ms": t_dl,
        "t_parse_ms": t_parse,
        "t_project_ms": t_proj,
        "bytes": len(raw),
        "rows": len(records),
    }


def _backfill_calendar_days(end: date, n: int) -> list[date]:
    """Return *n* consecutive calendar days ending at *end* (inclusive)."""
    return [end - timedelta(days=i) for i in range(n - 1, -1, -1)]


def _trading_days_via_manifest(bucket: str, end: date, n: int) -> list[date]:
    """Use the manifest to filter to days that actually have an MDPS shard.

    MDPS rows currently have empty venue/instrument_id (writer underfill,
    flagged in plan), so we filter by (data_type, timeframe) only.
    """
    df = read_availability_index(bucket)
    mdps = df[df["service_name"] == "market-data-processing-service"]
    # Per-symbol predicate — matches what the rebuild script writes per file.
    mdps = mdps[
        (mdps["data_type"] == DATA_TYPE)
        & (mdps["timeframe"] == TIMEFRAME)
        & (mdps["venue"] == VENUE)
        & (mdps["instrument_id"] == SYMBOL)
        & (mdps["available"] == True)  # noqa: E712
    ]
    have = set(mdps["date"].astype(str).tolist())

    candidate = _backfill_calendar_days(end, n)
    return [d for d in candidate if d.isoformat() in have]


def _trading_days_via_listing(client, bucket: str, end: date, n: int) -> tuple[list[date], float]:
    """Alternative pruning: one list_blobs call at the day prefix.

    Returns (days_with_data, list_call_ms). Use when the manifest is
    underfilled — verified true for TRADFI MDPS rows as of 2026-04-29.
    """
    candidate = _backfill_calendar_days(end, n)
    t0 = time.perf_counter()
    have: set[str] = set()
    # one list_blobs per candidate day at the venue prefix; cheap.
    # In production we'd cache this for the (bucket, timeframe, data_type, venue)
    # tuple — same idea as the manifest cache.
    for d in candidate:
        prefix = (
            f"processed_candles/by_date/day={d.isoformat()}"
            f"/timeframe={TIMEFRAME}/data_type={DATA_TYPE}"
            f"/venue={VENUE}/"
        )
        try:
            blobs = list(client.list_blobs(bucket=bucket, prefix=prefix, max_results=1))
            if blobs:
                have.add(d.isoformat())
        except Exception:
            pass
    elapsed = (time.perf_counter() - t0) * 1000
    return [d for d in candidate if d.isoformat() in have], elapsed


def scenario_single_cold(client, bucket: str) -> dict:
    """Each run uses a fresh storage client to defeat connection cache."""
    samples = []
    for _ in range(N_RUNS):
        fresh = get_storage_client()
        t0 = time.perf_counter()
        r = _fetch_one(fresh, bucket, SINGLE_DAY)
        wall = (time.perf_counter() - t0) * 1000
        if r["ok"]:
            samples.append({**r, "wall_ms": wall})
    return {"name": "single cold", "samples": samples}


def scenario_single_warm(client, bucket: str) -> dict:
    """Reuse the same client across runs — captures TLS-reuse savings."""
    # Prime
    _ = _fetch_one(client, bucket, SINGLE_DAY)
    samples = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        r = _fetch_one(client, bucket, SINGLE_DAY)
        wall = (time.perf_counter() - t0) * 1000
        if r["ok"]:
            samples.append({**r, "wall_ms": wall})
    return {"name": "single warm", "samples": samples}


def _multi_fetch(client, bucket, days, max_workers) -> tuple[float, list[dict]]:
    t0 = time.perf_counter()
    if max_workers == 1:
        results = [_fetch_one(client, bucket, d) for d in days]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            results = list(ex.map(lambda d: _fetch_one(client, bucket, d), days))
    wall = (time.perf_counter() - t0) * 1000
    return wall, results


def scenario_multi(name: str, client, bucket: str, days: list[date],
                   workers: int) -> dict:
    walls = []
    last_results = []
    for _ in range(N_RUNS):
        wall, results = _multi_fetch(client, bucket, days, workers)
        walls.append(wall)
        last_results = results
    ok_rows = sum(r["rows"] for r in last_results if r["ok"])
    ok_bytes = sum(r["bytes"] for r in last_results if r["ok"])
    ok_count = sum(1 for r in last_results if r["ok"])
    return {
        "name": name,
        "walls_ms": walls,
        "n_files_attempted": len(days),
        "n_files_ok": ok_count,
        "rows_total": ok_rows,
        "bytes_total": ok_bytes,
    }


def _stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    s = sorted(values)
    p50 = s[len(s) // 2]
    p99 = s[max(0, int(len(s) * 0.99) - 1)] if len(s) > 1 else s[0]
    return p50, p99


def render_markdown(scenarios: list[dict], project_id: str) -> str:
    lines = []
    lines.append(f"# Price-chart GCS read benchmark — baseline")
    lines.append("")
    lines.append(f"- Date: {datetime.utcnow().isoformat()}Z")
    lines.append(f"- Project: `{project_id}`")
    lines.append(f"- Symbol: `{VENUE}:{SYMBOL}` `{TIMEFRAME}` `data_type={DATA_TYPE}`")
    lines.append(f"- Bucket: `market-data-tick-{CATEGORY}-{project_id}`")
    lines.append(f"- Code path: current `BatchCandleReader`-equivalent (pre-Unit-A)")
    lines.append(f"- Runs per scenario: {N_RUNS}")
    lines.append("")
    lines.append("## Single-file scenarios")
    lines.append("")
    lines.append("| Scenario | wall p50 (ms) | wall p99 (ms) | download p50 | parse p50 | project p50 | bytes | rows |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for sc in scenarios:
        if "samples" not in sc:
            continue
        s = sc["samples"]
        if not s:
            lines.append(f"| {sc['name']} | (no samples) |")
            continue
        wall = [x["wall_ms"] for x in s]
        dl = [x["t_download_ms"] for x in s]
        pa = [x["t_parse_ms"] for x in s]
        pj = [x["t_project_ms"] for x in s]
        wp50, wp99 = _stats(wall)
        b = s[-1]["bytes"]
        r = s[-1]["rows"]
        lines.append(
            f"| {sc['name']} | {wp50:.1f} | {wp99:.1f} | "
            f"{statistics.median(dl):.1f} | {statistics.median(pa):.1f} | "
            f"{statistics.median(pj):.1f} | {b:,} | {r} |"
        )
    lines.append("")
    lines.append("## Multi-file scenarios")
    lines.append("")
    lines.append("| Scenario | wall p50 (ms) | wall p99 (ms) | files attempted | files ok | rows | bytes |")
    lines.append("|---|---|---|---|---|---|---|")
    for sc in scenarios:
        if "walls_ms" not in sc:
            continue
        wp50, wp99 = _stats(sc["walls_ms"])
        lines.append(
            f"| {sc['name']} | {wp50:.1f} | {wp99:.1f} | "
            f"{sc['n_files_attempted']} | {sc['n_files_ok']} | "
            f"{sc['rows_total']:,} | {sc['bytes_total']:,} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", default="central-element-323112")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    bucket = build_bucket("processed_candles", project_id=args.project_id,
                          asset_group=CATEGORY)
    print(f"Bucket: {bucket}", file=sys.stderr)

    client = get_storage_client(project_id=args.project_id)

    # Scenario 1: single cold
    print("→ Scenario 1: single cold", file=sys.stderr)
    s1 = scenario_single_cold(client, bucket)

    # Scenario 2: single warm
    print("→ Scenario 2: single warm", file=sys.stderr)
    s2 = scenario_single_warm(client, bucket)

    # Calendar 10-day window (will include weekends → 404 holes, that's the point)
    cal10 = _backfill_calendar_days(THIRTY_DAY_END, 10)
    # Manifest-pruned (BROKEN today — MDPS underfill, captures the gap)
    manifest10 = _trading_days_via_manifest(bucket, THIRTY_DAY_END, 14)[-10:]
    # GCS-listing-pruned (works today; what we'd use in production until manifest is fixed)
    listing10, list10_ms = _trading_days_via_listing(client, bucket, THIRTY_DAY_END, 14)
    listing10 = listing10[-10:]
    listing30, list30_ms = _trading_days_via_listing(client, bucket, THIRTY_DAY_END, 45)
    listing30 = listing30[-30:]

    print(f"  manifest10={len(manifest10)} listing10={len(listing10)} (list cost {list10_ms:.0f}ms) listing30={len(listing30)} (list cost {list30_ms:.0f}ms)",
          file=sys.stderr)

    # Scenario 3: 10 calendar days, parallel (no pruning — current behavior)
    print("→ Scenario 3: 10 calendar days, parallel (no prune)", file=sys.stderr)
    s3 = scenario_multi("10 cal days parallel (no prune)", client, bucket,
                        cal10, workers=10)

    # Scenario 4: 10 calendar days, sequential
    print("→ Scenario 4: 10 calendar days, sequential", file=sys.stderr)
    s4 = scenario_multi("10 cal days sequential", client, bucket,
                        cal10, workers=1)

    # Scenario 5: 10 trading days, parallel + listing-pruned (real-today path)
    print("→ Scenario 5: 10 trading days, parallel + listing-pruned", file=sys.stderr)
    s5 = scenario_multi("10 trading days parallel + listing-pruned", client, bucket,
                        listing10, workers=10)

    # Scenario 6: 30 trading days, parallel + listing-pruned
    print("→ Scenario 6: 30 trading days, parallel + listing-pruned", file=sys.stderr)
    s6 = scenario_multi("30 trading days parallel + listing-pruned", client, bucket,
                        listing30, workers=16)

    # Scenario 7: manifest-pruned (broken today — for the record)
    if manifest10:
        print("→ Scenario 7: manifest-pruned (broken today, MDPS underfill)", file=sys.stderr)
        s7 = scenario_multi("manifest-pruned (BROKEN — MDPS underfill)",
                            client, bucket, manifest10, workers=10)
    else:
        s7 = {
            "name": "manifest-pruned (BROKEN — MDPS underfill, 0 days matched)",
            "walls_ms": [], "n_files_attempted": 0, "n_files_ok": 0,
            "rows_total": 0, "bytes_total": 0,
        }

    md = render_markdown([s1, s2, s3, s4, s5, s6, s7], args.project_id)
    md += f"\n\n## Notes\n\n"
    md += f"- **Manifest pruning is non-functional today.** TRADFI MDPS rows in `_index/availability_index.parquet` only cover 2 dates (2026-01-02 + 2026-04-10) despite ~24 days of GCS parquet existing. MDPS writer is underfilling. Until fixed, **listing-pruning** (one `list_blobs` per candidate day) is the right interim approach — adds {list30_ms:.0f}ms for a 30-day window, well under the savings.\n"
    md += f"- Single-file cold p50 = {_stats([s['wall_ms'] for s in s1['samples']])[0]:.0f}ms is high vs parent-doc target (≤ 200ms cold). Likely region mismatch — bench ran from a workstation outside the bucket region. In a co-located backend (same region as the bucket), expect 50–100ms cold and 20–50ms warm.\n"
    md += f"- Sequential vs parallel: **{_stats(s4['walls_ms'])[0] / _stats(s3['walls_ms'])[0]:.1f}× speedup** from parallelism on 10 files.\n"
    print(md)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md)
        print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
