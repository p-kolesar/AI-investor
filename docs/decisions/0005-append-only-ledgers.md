# 5. Append-only ledgers; cash is the ledger's last row

Date: 2026-06-09 (documenting an earlier decision)
Status: Accepted

## Context

We need current cash and a trade history that's trustworthy and easy to reason
about, on top of whole-blob read-modify-write Parquet (no transactions).

## Decision

- **`trades.parquet`** is an append-only ledger — rows are never mutated.
- **`cash_ledger.parquet`** is append-only; a new dated row is appended on every
  trade, and **current cash = the last row's `amount`** (`row(-1)["amount"]`).
- **`portfolio.parquet`** is a *materialized* current-state view, rebuilt on each
  trade (a position row is dropped at 0 shares). It is derivable from the trade
  ledger but stored for fast reads.

## Consequences

- **Auditable history** — every cash change and trade is preserved in order.
- **Simple "current" reads** — last row for cash; the portfolio blob for positions
  — no aggregation on the read path.
- **Reconcilable** — net shares from `trades` must equal `portfolio` shares, and
  `cash_ledger` row count = 1 seed + N trades. (Verified against live data on
  2026-06-09 — see [data validation](../data/README.md).)
- **Cost** — `portfolio` is redundant state that must be kept consistent with the
  ledger; the single writer (`apply_trade`) is the only place that may write both.
- Don't reorder or rewrite ledger rows — readers assume chronological append order.
