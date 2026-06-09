# Data layer

Status: **current** · Last verified: 2026-06-09

This is the part of the system you **cannot read from the source tree**: the
data lives in an Azure Storage account, written and read at runtime. Get this
wrong and the agent corrupts the portfolio or the dashboard shows nonsense — so
this section documents every blob in full, with sample rows.

## The big picture

One **Azure Storage account** (the Function App's `AzureWebJobsStorage`) holds
the portfolio manager's entire state in a single blob container:

| Container | Purpose | Format | Writer | Reader | Schema |
| --- | --- | --- | --- | --- | --- |
| `papertrading` | The portfolio manager's whole state — positions, cash, trades, watchlist, agent runs, price cache, API-usage counter, benchmark | **Parquet** (Polars) | backend (`/setup`, `/trade`, agent loop, Finnhub client) | backend endpoints + frontend (via API) | [schemas/papertrading.md](schemas/papertrading.md) |

Details on the account, auth, and naming: [storage-account.md](storage-account.md).

> There is no relational database — Parquet blobs *are* the database.

## The data contract (read before touching storage)

These invariants are assumed by the code. Breaking one silently breaks the app:

1. **Parquet schemas are fixed by `/setup`.** [`admin_init`](../../backend/function_app.py)
   creates every blob with explicit column dtypes. Writers must preserve those
   columns and types. Appends use `how="diagonal_relaxed"`, which tolerates
   column *order* but not type drift.
2. **`cash_ledger.parquet` is append-only; the *last row* is the truth.** Current
   cash = `row(-1)["amount"]`. Never rewrite history; append a new dated row.
3. **`trades.parquet` is an append-only ledger.** Never mutate past trades.
4. **`portfolio.parquet` is a *materialized* current state**, rebuilt on every
   trade (a position row is dropped when shares reach 0). It is derivable from
   the trade ledger but stored for fast reads.
5. **`avg_cost` is unchanged on SELL**; only BUY recomputes the weighted average.
6. **Prices in trades come from a live quote, not the model** — the agent decides
   *what* to trade; the loop fetches the price and calls `apply_trade`.
7. **`finnhub_usage.parquet` is the persisted daily API-cap counter** and survives
   cold starts; the per-minute throttle is in-memory only.

## Sample data

`samples/papertrading/` holds a representative row set for every blob, as **CSV
mirrors** (even though storage is Parquet) so they are diff-able and readable in
review. They are synthetic but realistic and schema-accurate — safe to load into
a local storage emulator for testing. See the
[schema reference](schemas/papertrading.md) for the column meanings.
