# Sample data — `papertrading`

These are **real rows pulled from the dev storage account**
(`staiinvestordevjrvuk7pfk`) on **2026-06-09**, exported to CSV for
readability/diffability (production storage is Parquet). This is real
paper-trading demo data — no secrets or personal data.

| File | Contents |
| --- | --- |
| `portfolio.sample.csv` | **Full** live portfolio (11 positions). |
| `trades.sample.csv` | **Full** trade ledger (20 trades). |
| `cash_ledger.sample.csv` | **Full** cash ledger (21 rows; last row = current cash $4,684.80). |
| `watchlist.sample.csv` | **Full** live watchlist (19 symbols — agent-evolved, not the seed). |
| `finnhub_usage.sample.csv` | **Full** daily API-call counter (6 days). |
| `agent_log.sample.csv` | **Subset** — the 3 most recent runs. `memo` holds full markdown investment memos (Slovak), so rows are large; this is faithful to production. |
| `prices_cache.sample.csv` | **Subset** — first 8 of 34 cached symbols. The full cache is a superset of the watchlist (see schema note). |
| `benchmark.sample.csv` | **Synthetic** — the production blob is empty (stub for the future `/history` endpoint); this shows the intended shape. |
| `snapshots.sample.csv` | **Synthetic** — the snapshots blob is new (added with the Daily tab); the dev account has not yet accumulated rows. Shows 3 illustrative daily rows; `positions` is the JSON holdings list. |

## What still reconciles

The `portfolio` / `trades` / `cash_ledger` trio is the **full** real set, so the
data-contract relationships hold and can be verified against these files:

- Net shares from `trades` (BUY − SELL per symbol) equal `portfolio.shares` for
  all 11 positions.
- `cash_ledger` has 21 rows = 1 seed ($100,000) + 20 trades, last row = current cash.

The subset files (`agent_log`, `prices_cache`) and the synthetic `benchmark` /
`snapshots` are illustrative and do not need to reconcile against the trio.

To seed a local store, convert each CSV to Parquet with the dtypes in
[../../schemas/papertrading.md](../../schemas/papertrading.md) (or call
`GET /api/setup` for empty, correctly-typed blobs).
