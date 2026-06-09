# Architecture overview

Status: **current** · Last verified: 2026-06-09

An autonomous, paper-trading portfolio manager built as a live GenAI demo. A
Claude agent runs every weekday, scans a watchlist, decides trades, and writes
an investment memo. See the root [README.md](../../README.md) and
[AI Portfolio Manager Spec.md](../../AI%20Portfolio%20Manager%20Spec.md) for the
operational facts and the original (Slovak) design.

## Components

| Component | Tech | Doc |
| --- | --- | --- |
| Backend API + agent | Python Flex Consumption Function App | [backend.md](backend.md) |
| AI agent | Claude API (`claude-sonnet-4-6`), 2-level loop | [backend.md](backend.md) |
| Market data | Finnhub (rate-limited, 15-min cache) | [backend.md](backend.md) |
| State storage | Polars + Parquet in Azure Blob | [../data/README.md](../data/README.md) |
| Frontend | React + Vite SPA → Azure Static Web Apps | [frontend.md](frontend.md) |
| IaC / CI | Bicep + GitHub Actions | [infrastructure.md](infrastructure.md) |

## Data & control flow

```
Azure Functions timer (07:55, Mon–Fri)  ─┐   ← the daily run
POST /api/agent/run (manual trigger)     ├─► run_agent()
                                         ─┘        │
                                                     ▼
        Level 1 screening (prefetch quotes+recs ─► Claude ranks) 
                                                     │ selects 2–3
                                                     ▼
        Level 2 deep dive (Claude + Finnhub tools)  ─► trades + memo
                                                     │
                                                     ▼
        apply_trade() ─► portfolio / trades / cash_ledger  (Parquet)
        _log_run()    ─► agent_log                         (Parquet)
        _write_snapshot() ─► snapshots (live-marked)        (Parquet)
                                                     │
   React SPA  ◄── /api/portfolio,/trades,/snapshots,/agent/log,/watchlist ◄──┘
```

## TODO

- [ ] Expand the request/data-flow narrative with sequence detail.
- [ ] Add a component diagram (image) once the layout stabilizes.
