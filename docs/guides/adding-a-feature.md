# Adding a feature / fixing a bug

Status: **current** · Last verified: 2026-06-09

A short playbook for humans **and agents** working in this repo safely. The
recurring risk here is the **data layer**: storage is schema-on-write Parquet,
not a migrated database, so a careless column change corrupts state silently.

## Before you touch storage

1. Read the [data contract](../data/README.md#the-data-contract-read-before-touching-storage)
   and the [schema reference](../data/schemas/papertrading.md).
2. `/setup` defines the dtypes. If you add/rename/retype a column you must update
   `admin_init`, every writer, and decide how existing blobs migrate (there is no
   migration framework — usually a re-`/setup` on a fresh store, or a one-off
   backfill script).
3. Keep append-only blobs append-only (`trades`, `cash_ledger`).

## Workflow

1. Reproduce against realistic local state (seed from
   [samples](../data/samples/papertrading/)).
2. Make the change; keep [`api.js`](../../frontend-prod/src/api.js) the only
   frontend↔backend seam.
3. **Update docs in the same PR** — schema docs + samples if the data shape
   changed; the relevant architecture doc if behaviour changed; bump
   `Last verified:`.
4. Add/adjust tests in [`tests/`](../../tests/) and run the suite
   (`backend/.venv/Scripts/python.exe -m pytest`). See [testing.md](testing.md).
5. Record a [decision](../decisions/) if you made a non-obvious architectural choice.

## Worked example: add a `realized_pnl` column to `trades`

Goal: persist realized P&L on each SELL instead of computing it in the frontend.
This touches the full chain — a good template for any schema change.

1. **Schema (`/setup`)** — in [`function_app.py`](../../backend/function_app.py)
   `admin_init`, add `"realized_pnl": pl.Series([], dtype=pl.Float64)` to the
   `trades` DataFrame.
2. **Writer** — in [`trading.py`](../../backend/trading.py) `apply_trade`, compute
   `realized = (price - held_avg) * shares` on SELL (0.0 on BUY) and include it in
   the appended `new_trade` row. (Note `append_parquet`/`concat` uses
   `diagonal_relaxed`, so old rows without the column become null — decide if you
   backfill.)
3. **API** — `GET /api/trades` returns `to_dicts()`, so the new field flows out
   automatically. No endpoint change.
4. **Frontend** — `getTrades()` shape gains `realized_pnl`; you can now drop the
   client-side `realizedFromTrades` math in
   [Performance.jsx](../../frontend-prod/src/views/Performance.jsx) and read the
   field directly.
5. **Migration** — existing `trades.parquet` has no column. Either re-`/setup`
   (loses history — fine for a demo reset) or write a one-off script that reads,
   adds the column with a computed/zero default, and writes back.
6. **Docs** — update [trades schema](../data/schemas/papertrading.md), regenerate
   the [trades sample](../data/samples/papertrading/), note the frontend change in
   [frontend.md](../architecture/frontend.md).
7. **Test** — cover BUY (0), SELL (gain), SELL (loss), and the migration path.

## Known drifts to be aware of (don't trip on these)

- The agent **mandate rules are prompt-only, not enforced** — the agent can
  exceed the 15 %/position or 10 % cash floor. Don't assume code guards them.
- The daily agent run is the **Azure Functions timer** (`daily_agent_timer`);
  there is no GitHub scheduler. See [infrastructure.md](../architecture/infrastructure.md).
- Stored `market_value` is the last-trade value, not live — the frontend re-marks
  with live quotes.
