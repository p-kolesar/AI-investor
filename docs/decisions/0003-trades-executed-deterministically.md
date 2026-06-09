# 3. Trades are executed deterministically, not as a Claude tool

Date: 2026-06-09 (documenting an earlier decision)
Status: Accepted

## Context

The deep-dive agent decides what to trade. We could expose a `place_trade` tool
and let the model call it, or have the model only *propose* trades and let code
execute them.

## Decision

Trades are **not** a Claude tool. The deep-dive model emits a JSON `trades` block
(`symbol`, `side`, `shares`, `reasoning`); the loop in
[`agent/loop.py`](../../backend/agent/loop.py) then, for each trade,
**fetches a live quote for the price** and calls `apply_trade()`
([`trading.py`](../../backend/trading.py)) deterministically. The model never
sets the execution price.

## Consequences

- **Prices are trustworthy** — execution price comes from Finnhub, not a possibly
  hallucinated number in the model's output.
- **Validation is centralized** — `apply_trade` enforces cash/oversell rules and
  reconciles positions + cash + ledger the same way for the agent and the manual
  `/trade` endpoint.
- **Auditable** — the model's `reasoning` is captured per trade; the memo explains
  the rest.
- **Trade-off** — the model can propose an invalid trade (e.g. insufficient cash);
  those are caught and recorded in the run's `skipped` list rather than failing the
  run.
- Note the mandate's sizing/cash rules are still **prompt-only** — not enforced by
  `apply_trade`.
