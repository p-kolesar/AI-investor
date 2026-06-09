# Infrastructure & CI/CD

Status: **current** · Last verified: 2026-06-09

Azure resources via Bicep; deploys via GitHub Actions. Operational setup
(secrets, variables, deploy order) is in the root
[README](../../README.md#one-time-setup). This doc describes the *shape* and
calls out where reality differs from the README.

## Azure resources ([`infra/main.bicep`](../../infra/main.bicep))

Deployed at **resource-group scope** (the RG is created by the infra workflow first).

| Resource | Notes |
| --- | --- |
| Storage account | `Standard_LRS`, `StorageV2`, TLS 1.2, **public blob access off**. Names derived from `baseName`+`env`+`uniqueString`. |
| Blob containers | `deploymentpackage` (function deploy zips) and `papertrading` (app data). **No `datain`** — the real-estate container was removed. |
| Log Analytics + App Insights | App Insights wired to the workspace; connection string injected into the Function App. |
| Flex Consumption plan | `FC1`, Linux. |
| Function App | Linux Python `3.13`, **system-assigned managed identity**, max 40 instances / 2048 MB. CORS allows only the prod SWA origin. |
| Static Web App (prod) | `Free` tier, `provider: None` (deployed via token, no SWA-managed repo integration). |

### Function App settings (injected by Bicep)

`AzureWebJobsStorage` and `DEPLOYMENT_STORAGE_CONNECTION_STRING` are both set to a
**connection string** built from the storage account key — this is why the
storage code uses the connection-string path (see
[../data/storage-account.md](../data/storage-account.md)). Plus
`APPLICATIONINSIGHTS_CONNECTION_STRING`, `FINNHUB_API_KEY`, `CLAUDE_API_KEY`.

> `WEBSITE_TIME_ZONE` is **not** set by Bicep. The daily timer's NCRONTAB is
> interpreted in that zone — without it the timer fires at **07:55 UTC**, not CET
> (see below). Worth adding to the Bicep app settings.

## Workflows ([`.github/workflows/`](../../.github/workflows/))

All use `secrets.AZURE_CREDENTIALS` to log in and `vars.AZURE_RESOURCE_GROUP` to
locate resources.

| Workflow | Triggers | Does | Extra secrets/vars |
| --- | --- | --- | --- |
| `infra.yml` | push `infra/**`; manual | Create RG (idempotent) → `az deployment group create` Bicep → print func/SWA hostnames to the run summary. | `FINNHUB_API_KEY`, `CLAUDE_API_KEY`; vars `AZURE_LOCATION`, `AZURE_BASE_NAME`. |
| `deploy.yml` | push `backend/**`; manual | Discover the Function App in the RG → deploy `backend/` (remote build) → smoke-test `GET /api/health` (10× retry). | — |
| `deploy-frontend-prod.yml` | push `frontend-prod/**`; manual | Discover func host + SWA deploy token → `npm ci && build` with `VITE_API_BASE=https://<func-host>/api` → upload `dist` to the SWA. | — (token fetched at runtime) |
| `auto-fix-bug.yml` | issue labeled `bug` | Claude Code triages the issue → if clear, branches, fixes, runs pytest, updates tests/docs, opens a PR to main (draft if tests fail); else comments. See [../guides/automated-bug-fix.md](../guides/automated-bug-fix.md). | `CLAUDE_API_KEY` |

> There is **no daily-agent GitHub workflow** — it was obsolete (its cron was
> disabled to avoid double-running) and has been removed. The daily run is the
> Functions timer below.

## How the agent gets triggered

The daily run is an **Azure Functions timer trigger** — `daily_agent_timer` in
[`function_app.py`](../../backend/function_app.py), NCRONTAB `0 55 7 * * *`
(**07:55** in the app's `WEBSITE_TIME_ZONE`), weekdays only (skips Sat/Sun in
code). It calls the same `run_agent()` as `POST /api/agent/run`. Failures raise
and surface in Function App / Application Insights logs; cost-guardrail states
(`disabled`/`blocked`) are returned in the run result and recorded in
`agent_log`, but do **not** raise.

> **Known simplifications:**
> - `WEBSITE_TIME_ZONE` is not set by Bicep, so the timer currently fires at
>   07:55 **UTC**, not CET, until that app setting is added.
> - There is **no holiday calendar** — the timer skips weekends only, so it will
>   run on US market holidays (acceptable for a demo).

## TODO

- [ ] Add `WEBSITE_TIME_ZONE` to the Bicep app settings (CET intent).
- [ ] Document the second SWA (`frontend-beta`) when it's added.
