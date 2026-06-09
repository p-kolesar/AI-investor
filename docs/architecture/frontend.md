# Frontend

Status: **current** · Last verified: 2026-06-09

React + Vite SPA, dark mode, deployed to Azure Static Web Apps (Free).
Source: [`frontend-prod/`](../../frontend-prod/).

## Shape

- **Tab shell** — [`src/App.jsx`](../../frontend-prod/src/App.jsx) holds a `TABS`
  registry and swaps the active view. No router. Shows a "demo data" banner when
  running on stubs.
- **Single backend seam** — [`src/api.js`](../../frontend-prod/src/api.js) is the
  *only* module that talks to the API. Every view imports from it and nothing
  else. When `VITE_API_BASE` is unset it serves **stub data** with shapes that
  match the real endpoints 1:1, so the SPA runs with no backend.
- **Components** — [`src/components/`](../../frontend-prod/src/components/):
  `KpiCard`, `Charts`, `States` (Loading/Error/Empty), `useAsync` (fetch hook),
  `format.js` (usd/pct/num/signClass), `perf.js` (`realizedFromTrades`).

## Views → data dependencies

| View | API calls | Computed client-side |
| --- | --- | --- |
| [Dashboard](../../frontend-prod/src/views/Dashboard.jsx) | `getPortfolio`, `getHistory` | total return vs $100K; outperformance vs SPY over the charted window. |
| [Positions](../../frontend-prod/src/views/Positions.jsx) | `getPortfolio` + `getPrice` per symbol | **live** market value, unrealized P&L, P&L % — recomputed from live quotes (not the stored `market_value`). |
| [Daily](../../frontend-prod/src/views/Daily.jsx) | `getSnapshots()` | none — renders the backend's per-run snapshots (date/time split from `timestamp`, holdings from `positions`). `market_value` is already live-marked at snapshot time, so no per-symbol re-quote. Newest-first. |
| [Agent Log](../../frontend-prod/src/views/AgentLog.jsx) | `getAgentLog(30)` | master/detail timeline + selected memo; per-level token split. Expects runs **newest-first** (as the backend serves them). |
| [Performance](../../frontend-prod/src/views/Performance.jsx) | `getPortfolio`, `getTrades` + `getPrice` per symbol | win rate + realized P&L from the trade ledger (`realizedFromTrades`); unrealized from live prices. |

> **Why the frontend re-marks prices:** the backend's stored `market_value` is
> the *last-trade* value, not live (see the data contract). Positions and
> Performance therefore fetch a live quote per held symbol and compute P&L on the
> client.

## Known stubs (blocked on backend)

Driven by `getHistory()` in `api.js`, which **always** returns mock data flagged
`isStub: true` because there is no `/history` endpoint and `benchmark.parquet` is
empty:

- Dashboard "Portfolio vs SPY" line + "Daily P&L" bars (banner shown).
- Performance tab **Sharpe ratio** and **max drawdown** (placeholder panels:
  "pending history endpoint").

When the backend gains `GET /api/history → [{date, portfolio_value, spy_close}]`,
**only `getHistory()` changes** — no view edits. (Tracked in project memory:
backend time-series gap.)

## Config (dev vs prod)

| Var | Effect |
| --- | --- |
| (unset) | Stub/demo data, no backend. |
| `VITE_API_BASE=https://<func-host>/api` | Hit the live API cross-origin (prod build uses this; backend CORS allows the SWA origin). |
| `VITE_API_PROXY=http://localhost:7071` | Dev-only: proxy `/api` to a local backend to avoid CORS. |

The prod build (`deploy-frontend-prod.yml`) sets
`VITE_API_BASE=https://<func-host>/api` — the SPA calls the Function App
cross-origin, and the backend's CORS allows the SWA origin. There is no
SWA linked-backend resource.

## frontend-beta (planned)

A workshop "bug-hunt" copy. Per the code comments it will drop the
**Performance** tab from the `TABS` registry. Not yet in the repo. Document it
here once it lands.
