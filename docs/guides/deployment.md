# Deployment

Status: **current** · Last verified: 2026-06-09

The authoritative deployment order, secrets, and variables are in the root
[README → One-time setup / Deployment order](../../README.md#deployment-order),
and the workflow mechanics are in
[../architecture/infrastructure.md](../architecture/infrastructure.md). This
guide adds deploy-time gotchas.

## Order (first time)

1. **Infra** (`infra.yml`) — creates the RG, Function App, prod SWA, CORS. Reads
   func/SWA hostnames from the run summary.
2. **Deploy backend** (`deploy.yml`) — discovers the Function App, deploys
   `backend/`, smoke-tests `/api/health`.
3. **Initialize state** — `GET /api/setup` **once** (creates the Parquet blobs).
   The app will error on `/portfolio` etc. until this runs.
4. **Deploy frontend** (`deploy-frontend-prod.yml`) — builds with
   `VITE_API_BASE` pointed at the live API, uploads to the SWA.

After the first run, pushes to `main` trigger each pipeline by changed path.

## Common failure modes

| Symptom | Cause / fix |
| --- | --- |
| Frontend loads but shows the "demo data" banner | `VITE_API_BASE` was empty at build time → built on stubs. Re-run the frontend deploy after infra exists. |
| API calls fail with CORS errors | The SWA origin isn't in the Function App's `cors.allowedOrigins`. Bicep sets it to the prod SWA hostname; re-run infra if the SWA was recreated. |
| `/portfolio` returns 500 right after deploy | `/api/setup` not called yet — no Parquet blobs. |
| First request is slow | Flex Consumption cold start — expected for a demo. |
| Agent didn't run "on schedule" | The daily run is the **Functions timer** (`daily_agent_timer`); there is no GitHub scheduler. Check the Function App, and that `WEBSITE_TIME_ZONE` is set (else it fires at 07:55 **UTC**). See infrastructure.md. |
| Agent ran on a US holiday | Expected — the timer skips weekends only, there is no holiday calendar. |

## Rolling out a schema change to `papertrading`

There is **no migration framework**. For a Parquet schema change you either:
- **Reset** — call `/api/setup` (recreates empty, correctly-typed blobs; loses
  state — acceptable for a demo), or
- **Backfill** — run a one-off script that reads each affected blob, adds/retypes
  the column with a sensible default, and writes it back.

Always update the [schema docs](../data/schemas/papertrading.md) and samples in
the same change. See [adding-a-feature.md](adding-a-feature.md) for a worked
example.
