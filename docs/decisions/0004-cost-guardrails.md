# 4. Cost guardrails (token cap + cumulative spend cap)

Date: 2026-06-09 (documenting an earlier decision)
Status: Accepted

## Context

The agent runs autonomously every weekday and calls paid APIs (Claude + Finnhub).
A bug, a prompt-injection, or a runaway tool loop could otherwise rack up cost
unsupervised. This is a public demo on a tight budget.

## Decision

Layered, self-enforcing caps:

**Claude** ([`agent/loop.py`](../../backend/agent/loop.py)) —
- per-call `max_tokens` (screening 1024 / deep dive 4096),
- `DAILY_TOKEN_CAP = 20,000` blocks the deep dive if screening alone exceeds it,
- `SPEND_CAP_USD = 10.00` on cumulative `estimated_cost_usd` (summed from
  `agent_log`) **disables the agent entirely**,
- `MAX_TOOL_ROUNDS = 5` bounds the tool-use conversation.

**Finnhub** ([`market/finnhub.py`](../../backend/market/finnhub.py)) —
- `RATE_LIMIT_PER_MIN = 42` (in-memory sliding window),
- `DAILY_CALL_CAP = 200` persisted in `finnhub_usage.parquet` (survives cold
  starts),
- 15-min quote cache.

Cap states (`disabled`/`blocked`) are returned in the run result and recorded in
`agent_log`; they are logged but do not raise, so they surface via Function App /
Application Insights monitoring rather than a failed CI run.

## Consequences

- **Bounded worst-case spend** without manual monitoring.
- The spend cap is a **hard stop**: once tripped the agent stays disabled until
  someone intervenes (e.g. resets `agent_log` or raises the cap) — intentional.
- The per-minute Finnhub throttle is best-effort (in-memory, resets on cold
  start); the durable guarantee is the persisted daily call cap.
- Estimated cost uses fixed $3/$15 per-1M rates — revisit if the model or pricing
  changes.
