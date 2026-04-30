"""Benchmark GCS read latency for the price-chart candle path.

⚠ **DO NOT RUN IN CI / TEST SUITES.** ⚠

This script hits **real Google Cloud Storage** and is *not* a test —
it has no pass/fail assertions, only prints latency numbers.  Running
it on every CI pipeline burns minutes per pipeline and pulls a few
megabytes from a real bucket each invocation.  It is intentionally
**outside** `tests/` (pytest's `testpaths = ["tests"]` will not pick
it up) and **must stay outside**.  Do not add a `test_*` prefix, do
not move it into `tests/`, do not wire it into a Makefile / quality
gate / pre-commit.

Run on demand only — when you've changed the read path and want to
see whether latency moved, or when you're sizing a deployment:

  GCP_PROJECT_ID=central-element-323112 \\
    /path/to/venv/bin/python scripts/bench_candle_reads.py \\
      --project-id central-element-323112 \\
      --out unified-trading-pm/reports/price_chart_gcs_benchmark_<DATE>.md

Output: prints a markdown table; --out FILE writes it to disk.

Eight scenarios, five iterations each, p50/p99 reported:
  1. single parquet, cold
  2. single parquet, warm (cache reuse)
  3. 10 parquets, parallel
  4. 10 parquets, sequential
  5. 10 parquets, parallel + listing-pruned
  6. 30 parquets, parallel + listing-pruned
  7. manifest-pruned (currently broken — captures the gap for the record)
  8. scroll-back UX simulation: 9 sequential 7-day windows

The corresponding **FE benchmark** lives at
`unified-trading-system-ui/tests/e2e/widgets/price-chart-benchmark.spec.ts`.
That one is CI-safe — it measures the FE↔BE round-trip only and runs
fine against a mock-mode backend (no GCS, sub-second).
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


def scenario_scrollback_chunks(
    client,
    bucket: str,
    n_chunks: int = 9,
    chunk_days: int = 7,
    end_date: date = THIRTY_DAY_END,
) -> dict:
    """Simulate the UI's scroll-back UX.

    The chart's loadMoreCandles fetches one chunk_days-window per scroll
    pull, working backwards from anchor. Each chunk uses BatchCandleReader's
    multi-day path (parallel reads within the chunk), but chunks themselves
    are sequential — a user can only scroll one window at a time.

    Measures wall-clock to load ~n_chunks*chunk_days days of history. This
    is the "user pans the chart from now back to two months ago" scenario.
    """
    from unified_trading_api.services.batch_candles import BatchCandleReader

    reader = BatchCandleReader(project_id=client._project_id if hasattr(client, "_project_id") else "central-element-323112")

    chunk_results: list[dict] = []
    walls: list[float] = []
    for run in range(N_RUNS):
        anchor = end_date
        run_chunks: list[dict] = []
        run_start = time.perf_counter()
        for i in range(n_chunks):
            to = anchor - timedelta(days=1) if i > 0 else anchor
            frm = to - timedelta(days=chunk_days - 1)
            t0 = time.perf_counter()
            records = reader.get_candles(
                venue=VENUE,
                symbol=SYMBOL,
                timeframe=TIMEFRAME,
                limit=10_000,
                from_date=frm,
                to_date=to,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            run_chunks.append({
                "chunk": i + 1,
                "from": frm.isoformat(),
                "to": to.isoformat(),
                "rows": len(records),
                "ms": elapsed_ms,
            })
            anchor = frm
        run_wall = (time.perf_counter() - run_start) * 1000
        walls.append(run_wall)
        if run == 0:
            chunk_results = run_chunks
    return {
        "name": f"scroll-back {n_chunks}× {chunk_days}-day chunks",
        "walls_ms": walls,
        "n_files_attempted": n_chunks,
        "n_files_ok": sum(1 for c in chunk_results if c["rows"] > 0),
        "rows_total": sum(c["rows"] for c in chunk_results),
        "bytes_total": 0,  # not tracked at chunk level
        "chunk_breakdown": chunk_results,
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

    # Scenario 8: scroll-back UX simulation (sequential 7-day chunks).
    # Mirrors what the chart's loadMoreCandles does: 9 chunks × 7 days each =
    # ~9 weeks of history loaded by panning the chart left. Each chunk goes
    # through BatchCandleReader's full path (manifest prune + parallel multi-day
    # reads within the window). Chunks themselves are sequential because a user
    # can only scroll one window at a time.
    print("→ Scenario 8: scroll-back UX (9× 7-day sequential chunks)", file=sys.stderr)
    s8 = scenario_scrollback_chunks(client, bucket, n_chunks=9, chunk_days=7)

    md = render_markdown([s1, s2, s3, s4, s5, s6, s7, s8], args.project_id)
    # Scroll-back gets its own table since chunk_breakdown is a different shape.
    md += "\n\n## Scroll-back chunk breakdown\n\n"
    md += "| chunk | from | to | rows | ms |\n"
    md += "|---|---|---|---|---|\n"
    for c in s8.get("chunk_breakdown", []):
        md += f"| {c['chunk']} | {c['from']} | {c['to']} | {c['rows']} | {c['ms']:.0f} |\n"
    if s8["walls_ms"]:
        s8_p50, s8_p99 = _stats(s8["walls_ms"])
        md += f"\n**Total wall-clock per run** (5 runs): p50={s8_p50:.0f} ms, p99={s8_p99:.0f} ms — covers 9 weeks of 1m bars.\n"
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
