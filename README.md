# AI Portfolio Manager

An autonomous, paper-trading portfolio manager built as a live GenAI demo. A
Claude agent runs every weekday, scans a watchlist, decides trades, and writes
an investment memo — all backed by a Python Azure Function App, with a React
dashboard on Azure Static Web Apps. See [AI Portfolio Manager Spec.md](AI%20Portfolio%20Manager%20Spec.md)
for the full design (Slovak).

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python Flex Consumption Function App |
| AI agent | Claude API — `claude-sonnet-4-6` |
| Market data | Finnhub (rate-limited + 15-min cache) |
| Storage | Polars + Parquet in Azure Blob Storage |
| Frontend | React + Vite SPA → Azure Static Web Apps (Free) |
| IaC / CI | Bicep + GitHub Actions |

## Layout

```
.github/workflows/
  infra.yml                 # provisions/updates Azure infra (infra/** + manual)
  deploy.yml                # deploys the Python function code (backend/** + manual)
  deploy-frontend-prod.yml  # builds + deploys frontend-prod to its Static Web App
infra/
  main.bicep                # Storage, Log Analytics + App Insights, Flex Consumption
                            # Function App (+ CORS), Free Static Web App (prod)
  main.parameters.json      # baseName / environmentName / pythonVersion
backend/
  function_app.py           # Python v2 HTTP endpoints (see below) + daily timer trigger
  agent/                    # loop.py (2-level agent), tools.py, prompts.py
  market/finnhub.py         # Finnhub wrapper: rate limit, daily cap, 15-min cache
  storage/blobs.py          # Parquet <-> Azure Blob helpers
  trading.py                # paper-trade validation + position/cash reconciliation
  host.json, requirements.txt, .funcignore
  local.settings.json.example
frontend-prod/              # React + Vite dashboard (dark mode), 4 tabs
  src/App.jsx               # tab shell
  src/api.js                # single backend seam (+ stub data when no API configured)
  src/views/                # Dashboard, Positions, AgentLog, Performance
  src/components/           # KpiCard, Charts, States, hooks, formatters
  vite.config.js, staticwebapp.config.json, .env.example
docs/                       # documentation: data layer, architecture, guides, ADRs — see docs/README.md
tests/                      # offline unit tests for key backend modules — see tests/README.md
```

> **New to the repo (human or agent)?** Start at [CLAUDE.md](CLAUDE.md) →
> [docs/README.md](docs/README.md). The data layer (`docs/data/`) is the part you
> can't infer from the code.

## Backend endpoints

All routes are served under `/api`.

| Endpoint | Method | Description |
| --- | --- | --- |
| `/setup` | GET | Initialize Parquet files, $100K cash, seed watchlist |
| `/portfolio` | GET | Current positions + cash + total value |
| `/trade` | POST | Record a BUY/SELL and reconcile positions + cash |
| `/trades` | GET | Trade ledger (append-only) |
| `/snapshots` | GET | Daily portfolio+cash snapshots (live-marked). `?limit=N` |
| `/snapshot` | GET | Snapshot the **current** portfolio on demand (live-marked; no agent run, no Claude/trades) |
| `/agent/run` | POST | Trigger one agent run (screening → deep dive → trades + memo) |
| `/agent/log` | GET | Recent runs (memo, tokens, cost) + cumulative spend. `?limit=N` |
| `/watchlist` | GET | Current agent-managed watchlist |
| `/prices/{symbol}` | GET | Live quote via 15-min cache |
| `/health` | GET | Liveness probe |

## One-time setup

### 1. Service principal → GitHub secret

Create a service principal with Contributor at **subscription** scope (so the
infra job can create the resource group) and save the JSON as the
`AZURE_CREDENTIALS` Actions secret:

```bash
az ad sp create-for-rbac \
  --name "gh-aiinvestor" \
  --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID> \
  --sdk-auth
```

### 2. Repository secrets

**Repo → Settings → Secrets and variables → Actions → Secrets**:

| Secret | Used by |
| --- | --- |
| `AZURE_CREDENTIALS` | all Azure workflows (login) |
| `FINNHUB_API_KEY` | infra (injected into the Function App) |
| `CLAUDE_API_KEY` | infra (injected into the Function App) |

### 3. Repository variables

**Repo → Settings → Secrets and variables → Actions → Variables**:

| Variable | Value |
| --- | --- |
| `AZURE_RESOURCE_GROUP` | `rg-aiinvestor-dev` |
| `AZURE_LOCATION` | `westeurope` *(must be a Static Web Apps region)* |
| `AZURE_BASE_NAME` | `aiinvestor` |

## Deployment order

1. **Infra (Bicep)** — Actions → *Infra (Bicep)* → Run. Creates the resource
   group, Function App, and the prod Static Web App; sets CORS so the SWA can
   call the API. The run summary prints the Function App + frontend hostnames.
2. **Deploy (Function code)** — discovers the Function App in the resource group,
   deploys `backend/`, and smoke-tests `GET /api/health`.
3. **Initialize state** — call `GET /api/setup` once to create the Parquet files,
   $100K cash, and seed watchlist.
4. **Deploy Frontend (prod)** — builds `frontend-prod` with `VITE_API_BASE`
   pointed at the live API and uploads to the Static Web App. (Fetches the SWA
   deploy token at run time — no extra secrets.)

After the first run, pushes to `main` trigger each pipeline by changed path
(`infra/**`, `backend/**`, `frontend-prod/**`). The **daily agent run is an Azure
Functions timer trigger** (`daily_agent_timer` in `backend/function_app.py`) that
fires at 07:55 (in the app's `WEBSITE_TIME_ZONE`; set it to a CET zone, else UTC),
Mon–Fri. Failures surface in Function App / Application Insights logs; cost
guardrails (spend/token cap) are recorded in the run result and the agent log.

## Cost guardrails

- **Claude:** per-call max tokens (screening 1024 / deep dive 4096), daily token
  cap (20K, runaway guard), cumulative spend cap ($10 → agent disables itself).
- **Finnhub:** ~42 calls/min throttle, 200 calls/day hard cap, 15-min quote cache.
- **Azure:** Flex Consumption; set a cost alert/budget on the subscription.

## Local development

### Backend

```bash
cd backend
python -m venv .venv; .venv\Scripts\activate   # Windows (PowerShell)
pip install -r requirements.txt
cp local.settings.json.example local.settings.json   # then fill in your keys
func start    # requires Azure Functions Core Tools v4
# GET http://localhost:7071/api/health  ->  {"status": "ok"}
```

> The `local.settings.json.example` is a template — put real keys only in the
> gitignored `local.settings.json`, never in the example.

### Frontend

```bash
cd frontend-prod
npm install
npm run dev          # runs on stub/demo data with no backend
```

To point the dev server at a real backend, set in `.env`:

```
# call the deployed API directly (CORS is configured for the SWA origin)
VITE_API_BASE=https://<func-host>/api
# or proxy /api to a local backend to avoid CORS during dev
VITE_API_PROXY=http://localhost:7071
```

## Status

| Component | State |
| --- | --- |
| Backend (agent, endpoints, storage) | ✅ done |
| Infra (Function App + prod SWA + CORS) | ✅ done |
| `frontend-prod` (4-tab dashboard) | ✅ done & deployed |
| Daily agent (Functions timer trigger) | ✅ operational |
| `frontend-beta` (workshop bug-hunt copy) | ⏳ planned |
| Dashboard charts on real data | ⏳ uses demo series until a `/history` endpoint exists |

> **Charts note:** the Dashboard portfolio-vs-SPY line and daily-P&L bar charts
> run on demo data (the backend has no daily time-series endpoint yet). Only
> `frontend-prod/src/api.js` `getHistory()` changes when that lands — the UI does
> not. Sharpe ratio / max drawdown on the Performance tab are stubbed for the
> same reason.

## Notes

- **Auth:** the frontend is a public URL with no authentication (by design).
- **Cold start:** Flex Consumption has a brief cold start — fine for a demo.
- **Init:** always call `GET /api/setup` before the first agent run.
