# `papertrading` container — schemas

Status: **current** · Last verified: 2026-06-12

All blobs are Parquet written by Polars. Column dtypes below are the **Polars
dtypes set by [`/setup`](../../../backend/function_app.py)**; preserve them.
Sample rows: [../samples/papertrading/](../samples/papertrading/).

---

## `portfolio.parquet` — current positions (materialized)

Rebuilt on every trade. One row per open position; the row is **dropped** when
shares reach 0.

| Column | Dtype | Meaning |
| --- | --- | --- |
| `symbol` | Utf8 | Ticker (uppercase), e.g. `AAPL`. |
| `shares` | Int64 | Shares currently held (> 0). |
| `avg_cost` | Float64 | Weighted-average cost basis. Recomputed on BUY, **unchanged on SELL**. Rounded to 4 dp. |
| `market_value` | Float64 | `shares × last trade price`, rounded to 2 dp. Not live-marked; refreshed only when a trade touches the position. |

Read by `GET /api/portfolio` (with cash → `total_value`). Written by
`apply_trade` ([trading.py](../../../backend/trading.py)).

---

## `trades.parquet` — trade ledger (append-only)

| Column | Dtype | Meaning |
| --- | --- | --- |
| `date` | Date | Trade date (`datetime.now().date()`). |
| `symbol` | Utf8 | Ticker (uppercase). |
| `shares` | Int64 | Shares transacted (> 0; always positive — direction is in `side`). |
| `price` | Float64 | Execution price per share. |
| `side` | Utf8 | `BUY` or `SELL`. |

Served by `GET /api/trades`. Never mutate existing rows.

---

## `watchlist.parquet` — agent-managed universe

| Column | Dtype | Meaning |
| --- | --- | --- |
| `symbol` | Utf8 | Ticker. |

Single column. The agent adds/removes symbols (size-capped at `MAX_WATCHLIST=30`;
never removes a symbol with an open position; validates adds with a live quote).
Seeded with 14 sector-diversified tickers by `/setup`. Served by `GET /api/watchlist`.

> **The live watchlist diverges from the seed.** Because the agent grows and
> prunes it every run, the production list is **not** the 14-symbol seed —
> e.g. the dev account currently holds 19 symbols (MSFT, NVDA, AMZN, GOOGL, LLY,
> META, AVGO, PANW, TSM, ANET, ORCL, CRWD, APP, AXON, PLTR, UBER, SPOT, COST,
> AMAT), tilted toward AI/tech names the agent has favoured. Don't assume the
> seed composition when reasoning about current state — read the blob.

---

## `cash_ledger.parquet` — cash balance over time (append-only)

| Column | Dtype | Meaning |
| --- | --- | --- |
| `date` | Date | Date of the balance change. |
| `amount` | Float64 | Cash balance **after** the change, rounded to 2 dp. |

**The last row is the current cash balance** (`row(-1)["amount"]`). Seeded at
`$100,000`. A new row is appended on every trade.

---

## `agent_log.parquet` — agent run history

One row per `run_agent()` execution.

| Column | Dtype | Meaning |
| --- | --- | --- |
| `run_date` | Date | When the run executed. |
| `level1_input_tokens` | Int64 | Screening call input tokens. |
| `level1_output_tokens` | Int64 | Screening call output tokens. |
| `level2_input_tokens` | Int64 | Deep-dive (tool-use) input tokens, summed over rounds. |
| `level2_output_tokens` | Int64 | Deep-dive output tokens, summed over rounds. |
| `total_tokens` | Int64 | Sum of all four token counts. |
| `estimated_cost_usd` | Float64 | `_cost()` at $3/1M in, $15/1M out. Rounded to 6 dp. |
| `memo` | Utf8 | The agent's prose memo (Slovak), or a `BLOCKED:` / status note. |

Served by `GET /api/agent/log` (returns recent runs + `cumulative_cost_usd =
sum(estimated_cost_usd)`). The cumulative sum drives the **$10 spend cap** that
disables the agent.

---

## `snapshots.parquet` — daily portfolio snapshots (append-only)

Written by `_write_snapshot` ([agent/loop.py](../../../backend/agent/loop.py)):
once at the end of every `run_agent()` run, and on demand via `GET /api/snapshot`
(`snapshot_portfolio()` — no agent/Claude calls, just current portfolio + live
quotes). Backs the frontend **Daily** tab via `GET /api/snapshots`.

| Column | Dtype | Meaning |
| --- | --- | --- |
| `timestamp` | Datetime | When the snapshot was taken (`datetime.now()` at run end). |
| `positions` | Utf8 | JSON list of held positions: `[{"symbol","shares"}]`. `[]` when all cash. |
| `market_value` | Float64 | Sum of positions valued at a **live** quote fetched at snapshot time (falls back to the stored last-trade value if a symbol can't be priced). Rounded 2 dp. |
| `cash` | Float64 | Free cash balance — last row of `cash_ledger.parquet`. Rounded 2 dp. |
| `total` | Float64 | `market_value + cash`. Rounded 2 dp. |

> Unlike `portfolio.parquet`, `market_value` here is **live-marked**, so `total`
> is the true portfolio value at run time. Append-only — never mutate past rows.
> The spend-cap-disabled early return in `run_agent` does **not** snapshot (the
> agent never ran); every other path does, so a day can have more than one row.

---

## `prices_cache.parquet` — Finnhub quote cache (15-min TTL)

One row per symbol (replaced on refresh — the writer filters out the old row,
then appends the new one).

> **The cache is never pruned — it is a superset of the watchlist, not a subset.**
> Every symbol the client ever quotes gets a row that stays forever, even after
> the symbol leaves the watchlist or its 15-min TTL expires. So
> `prices_cache.parquet` accumulates over time and will contain de-listed /
> dropped tickers (e.g. the dev account caches 34 symbols against a 19-symbol
> watchlist — TSLA, AMD, MSTR, CELH, RDDT, etc. linger). Do **not** treat the
> cache as "current watchlist prices": filter by `timestamp` for freshness and
> by the watchlist blob for membership.

| Column | Dtype | Meaning |
| --- | --- | --- |
| `symbol` | Utf8 | Ticker. |
| `price` | Float64 | Current price (Finnhub `c`). |
| `open` | Float64 | Day open (`o`). |
| `high` | Float64 | Day high (`h`). |
| `low` | Float64 | Day low (`l`). |
| `timestamp` | Datetime | When fetched. A row is a cache **hit** if `timestamp > now - 15 min`. |

> No volume column — Finnhub `/quote` has no volume field (noted in `/setup`).

---

## `finnhub_usage.parquet` — daily API-call counter (persisted cap)

| Column | Dtype | Meaning |
| --- | --- | --- |
| `date` | Date | Day. |
| `calls` | Int64 | Calls made that day. Cap = `DAILY_CALL_CAP = 200`; exceeding it raises. |

Created lazily by the Finnhub client (not by `/setup`). The per-minute throttle
(`RATE_LIMIT_PER_MIN = 42`) is in-memory only and resets on cold start; this
counter is the durable daily cap.

---

## `benchmark.parquet` — SPY daily close (forward-built)

| Column | Dtype | Meaning |
| --- | --- | --- |
| `date` | Date | Trading day (upsert — one row per day). |
| `close` | Float64 | SPY price captured at snapshot time (live quote, used as the day's close). |

Created empty by `/setup`, then **populated forward** by `_record_benchmark`
([agent/loop.py](../../../backend/agent/loop.py)), called from `_write_snapshot`
on every agent run / on-demand snapshot. **The first row is the inception
baseline** against which the agent's alpha is measured. History is *not*
backfillable — Finnhub's free tier blocks historical candles (`/stock/candle`
returns 403) — so a `/setup` reset restarts the SPY series from that day. Read by
`_compute_performance`, which feeds portfolio-vs-SPY alpha + per-position P&L into
the deep-dive prompt so each memo opens with its performance.
