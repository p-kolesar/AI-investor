# Backend

Status: **current** · Last verified: 2026-06-10

Python v2 Azure Function App (Flex Consumption). Source: [`backend/`](../../backend/).
The HTTP endpoint table lives in the root [README](../../README.md#backend-endpoints);
this doc covers how the pieces fit together.

## Modules

| Module | Responsibility |
| --- | --- |
| [`function_app.py`](../../backend/function_app.py) | HTTP routes + the daily timer trigger. Thin — delegates to the modules below. |
| [`agent/loop.py`](../../backend/agent/loop.py) | The autonomous agent: 2-level loop, guardrails, watchlist management, deterministic trade execution. |
| [`agent/prompts.py`](../../backend/agent/prompts.py) | `MANDATE` system prompt + the screening / deep-dive user prompts (Slovak). |
| [`agent/tools.py`](../../backend/agent/tools.py) | Claude tool definitions (Finnhub-backed) + dispatcher. Deep-dive only. |
| [`market/finnhub.py`](../../backend/market/finnhub.py) | Finnhub wrapper: rate limit, daily cap, 15-min quote cache. |
| [`trading.py`](../../backend/trading.py) | `apply_trade` — validation + position/cash reconciliation. Shared by `/trade` and the agent. |
| [`storage/blobs.py`](../../backend/storage/blobs.py) | Parquet read/write/append over Azure Blob. |

## The agent loop (`run_agent`)

`run_agent()` runs one daily cycle. Model: `claude-sonnet-4-6`. The system
prompt (`MANDATE`) is sent with `cache_control: ephemeral` on every call.

```
0. Read agent_log → if cumulative estimated_cost_usd ≥ $5  → return {status: disabled}
1. Load watchlist, portfolio (positions + held symbols), current cash
2. LEVEL 1 — SCREENING (one model call, no tools)
   • prefetch quote + analyst recommendation for EVERY watchlist symbol (Finnhub, cheap)
   • Claude ranks them → JSON {selected, add, remove, rationale}
   • keep selected ∩ watchlist; apply watchlist add/remove (validate adds via live quote,
     cap 30, never remove a held symbol)
   • if level-1 tokens ≥ 20,000  → return {status: blocked}   (runaway guard)
   • if nothing selected          → return {status: ok, selected: []}
3. LEVEL 2 — DEEP DIVE (tool-use conversation, ≤ 5 rounds)
   • Claude calls Finnhub tools for the 2–3 selected names → JSON trades block + prose memo
4. EXECUTE trades deterministically: for each, fetch a LIVE quote for the price,
   then apply_trade(). The model never sets the price.
5. _log_run() → append a row to agent_log.parquet
6. _write_snapshot() → append a live-marked portfolio+cash row to snapshots.parquet
   (runs on the blocked / nothing-selected / executed paths — every path past step 1;
    the step-0 disabled return does not snapshot). Backs the Daily tab.
```

### Guardrails (constants in `loop.py`)

| Guard | Value | Effect |
| --- | --- | --- |
| `SPEND_CAP_USD` | $5.00 | Cumulative `estimated_cost_usd` ≥ cap → agent **disables** itself (no calls). |
| `DAILY_TOKEN_CAP` | 20,000 | If screening alone exceeds it, the deep dive is **blocked** for the day. |
| `SCREENING_MAX_TOKENS` | 1,024 | `max_tokens` for the level-1 call. |
| `DEEPDIVE_MAX_TOKENS` | 4,096 | `max_tokens` per level-2 round. |
| `MAX_TOOL_ROUNDS` | 5 | Hard stop on the tool-use conversation. |
| `MAX_WATCHLIST` | 30 | Watchlist size cap. |
| Cost model | $3 / 1M input, $15 / 1M output | `_cost()` → `estimated_cost_usd`. |

### The JSON contracts the model must emit

**Level 1 (screening)** — `_extract_json` parses one object:
```json
{"selected": ["SYM", ...],
 "add":    [{"symbol": "SYM", "reason": "..."}],
 "remove": [{"symbol": "SYM", "reason": "..."}],
 "rationale": "..."}
```

**Level 2 (deep dive)** — a fenced JSON trades block **first** (so it isn't
truncated), then the free-text memo:
````
```json
{"trades": [{"symbol": "SYM", "side": "BUY", "shares": N, "reasoning": "1 sentence"}]}
```
<investment memo as prose…>
````
`_extract_json` reads the trades block; `_memo_after_json` strips it and keeps
the prose as the `memo`. Tolerant of ` ```json ` fences and bare `{…}`.

### The mandate (business rules, from `prompts.py`)

$100K start · US equities + ETFs · self-managed watchlist (≤ 30) · **5–10 open
positions** · **≤ 15 % per position** · **≥ 10 % cash reserve** · reduce to ≤ 5 %
two business days before earnings · benchmark = SPY · every decision (including
"do nothing") needs a written rationale. These rules live only in the prompt —
they are **not enforced in code**, so the agent can violate them (the sample
`agent_log` shows a run where cash fell below the 10 % floor). Treat them as
soft guidance, not invariants.

## Tools (deep dive only)

`DEEPDIVE_TOOLS`: `get_quote`, `get_fundamentals`, `get_news`,
`get_insider_sentiment`, `get_analyst_recommendation`, `get_price_target`,
`get_earnings` — all `{symbol}` → structured dict via `FinnhubClient`. Level 1
needs no tools because the loop pre-fetches quote + recommendation itself.
Trades are deliberately **not** a tool (see the deterministic-execution ADR).

## Data written

Every write targets the `papertrading` container — see
[../data/schemas/papertrading.md](../data/schemas/papertrading.md) and the
[data contract](../data/README.md#the-data-contract-read-before-touching-storage).
