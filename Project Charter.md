# Project Charter — &lt;PROJECT NAME&gt;

> **Clean-slate template.** This repo ships as a deployable shell: a Python
> Azure Function App (Flex Consumption) + a React/Vite SPA + Bicep infra +
> GitHub Actions CI/CD. The **shell sections** below are already true of the
> code in this repo — leave them as-is unless you change the stack. Fill in the
> **`> FILL IN`** sections with your business context, then build.

**Status:** draft v0 — _set a date and owner._
**Owner:** &lt;you&gt;

---

## 1. Purpose & scope

> FILL IN — What does this system do, for whom, and why? What is explicitly
> **out** of scope for v1? Keep it to a few sentences; everything below should
> derive from this.

---

## 2. Use cases (the driver)

> FILL IN — List the concrete use cases that justify the build. Everything in
> the data model, endpoints, and agent design should trace back to one of these.

| ID | Use case | Output | Notes |
|----|----------|--------|-------|
| UC1 | … | … | … |
| UC2 | … | … | … |

---

## 3. Stack _(shell — pre-wired)_

| Layer | Technology | In the shell? |
|-------|-----------|---------------|
| Backend | Python Function App (Flex Consumption) | ✅ `backend/` |
| API surface | Azure Functions Python v2 HTTP routes | ✅ `/api/hello`, `/api/health` |
| AI agent | Claude API (`CLAUDE_API_KEY` already wired into infra + settings) | ⛔ add `anthropic` + your loop |
| Storage | _(none yet)_ — add Azure Blob / Parquet / DB as needed | ⛔ |
| Frontend | React + Vite SPA → Azure Static Web Apps (Free) | ✅ `frontend-prod/` |
| IaC / CI | Bicep + GitHub Actions (infra / backend / frontend deploy) | ✅ `infra/`, `.github/workflows/` |

> FILL IN — Add the rows your project needs (market data API, database, queue,
> external services) and the corresponding secrets/app settings.

---

## 4. Repo structure _(shell)_

```
backend/
  function_app.py            # HTTP routes — currently /hello + /health
  host.json, requirements.txt, .funcignore
  local.settings.json.example
infra/
  main.bicep                 # Storage + Log Analytics/App Insights + Flex
                             # Function App (+CORS) + Free Static Web App
  main.parameters.json       # baseName / environmentName / pythonVersion
frontend-prod/               # React + Vite SPA (dark theme)
  src/App.jsx                # bare shell view
  src/api.js                 # single backend seam (stub data when no API)
  vite.config.js, staticwebapp.config.json, .env.example
.github/workflows/
  infra.yml                  # provision/update Azure infra
  deploy.yml                 # deploy the Function code (+ /health smoke test)
  deploy-frontend-prod.yml   # build + deploy the SPA to its Static Web App
```

> FILL IN — Note any new top-level modules you add (e.g. `backend/agent/`,
> `backend/storage/`, a data container in `infra/main.bicep`).

---

## 5. Backend endpoints

_Shell ships with:_

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/hello` | GET | Hello-world trigger (`?name=` optional) |
| `/health` | GET | Liveness probe — used by the deploy smoke test |

> FILL IN — Add your routes here as you build them. Keep `/health` (the deploy
> workflow smoke-tests it).

---

## 6. Data model

> FILL IN — Define your storage layout (containers/tables/Parquet files), the
> grain of each, keys, and mutability. The shell has **no** storage wired yet.

---

## 7. AI agent

> FILL IN — If this project uses a Claude agent: mandate, operating mode
> (autonomous / on-demand / both), tool catalog, and guardrails. `CLAUDE_API_KEY`
> is already injected into the Function App by `infra/main.bicep`. Add the
> `anthropic` package to `backend/requirements.txt` and your agent module under
> `backend/`.

### Guardrails _(pattern to reuse)_
> FILL IN — token + spend caps, max tool rounds, read-only vs. write tools,
> token logging. Keep all arithmetic out of the model.

---

## 8. Deployment _(shell — works today)_

1. **Infra (Bicep)** — Actions → *Infra (Bicep)* → Run. Creates the resource
   group, Function App, and the prod Static Web App; wires CORS.
2. **Deploy (Function code)** — deploys `backend/` and smoke-tests `/api/health`.
3. **Deploy Frontend (prod)** — builds `frontend-prod` against the live API and
   uploads to the Static Web App.

Required GitHub **secrets**: `AZURE_CREDENTIALS`, `CLAUDE_API_KEY`.
Required GitHub **variables**: `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`
(a Static Web Apps region), `AZURE_BASE_NAME`. See `README.md` for details.

---

## 9. Cost & guardrails

> FILL IN — Expected run-rate and the hard ceilings that enforce it (per-call
> token caps, cumulative spend cap, external-API rate/day caps, an Azure budget
> alert). Pattern: only the agent should cost model tokens; do data work in
> plain Python.

---

## 10. Open decisions

> FILL IN — Decisions still to make, each with a proposed default.
1. …
2. …
