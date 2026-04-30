# Live-universe sample fixtures (test mirror)

Mirror of `unified-trading-system-ui/lib/mocks/fixtures/live-universe/*.sample.json`.
Captured 2026-04-30 from a real backend boot reading GCS.

## Why duplicated here

The UI repo's mock-handler imports its own copy at build time. The
backend's tests need the same shape to validate schema parity end-to-end.
Symlinking across repo boundaries is fragile (workspace layout assumed,
breaks in CI). Copying is the cheapest correct option.

## When to refresh

Whenever the UI's `*.sample.json` files are regenerated. From the UI repo:

```bash
# 1. Regenerate UI sample fixtures (see UI repo README)
# 2. Copy into this dir:
cp ../unified-trading-system-ui/lib/mocks/fixtures/live-universe/*.sample.json \
   unified-trading-api/tests/fixtures/live-universe/
```

The schema-parity test (`tests/integration/test_live_universe_schema.py`)
catches drift either way:

- New field appears in real GCS → next regen lands a column UAC doesn't
  know → UAC validation fails loud.
- UAC adds a required field that real GCS doesn't yet emit → fixture
  validation against UAC fails loud.

## What's in here

| File | Asset group | Rows | Cols | Notes |
|------|-------------|------|------|-------|
| `cefi.sample.json` | cefi | 60 | 30 | 10 system-watchlist keys + 50 extras |
| `tradfi.sample.json` | tradfi | 60 | 30 | same |
| `defi.sample.json` | defi | 60 | 40 | DeFi has 10 extra on-chain columns (pool_address, contract_addresses, decimals…) |
