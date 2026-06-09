# Local development

Status: **current** · Last verified: 2026-06-09

The canonical steps live in the root
[README → Local development](../../README.md#local-development). This guide adds
the data-specific bits.

## Backend

1. Create the venv and install deps (root README), then copy
   `local.settings.json.example` → `local.settings.json` and fill in keys.
2. **Storage:** point `AzureWebJobsStorage` at either
   - **Azurite** (local emulator): `UseDevelopmentStorage=true` — the example
     file ships this commented out, or
   - a **real dev storage account** connection string (what the live dev app uses).
   The storage code needs a *connection string* (not identity) — see
   [../data/storage-account.md](../data/storage-account.md).
3. `func start`, then `GET http://localhost:7071/api/setup` **once** to create the
   Parquet blobs ($100K cash, 14-symbol seed watchlist).
4. To start from realistic state instead of empty, convert the
   [sample CSVs](../data/samples/papertrading/) to Parquet using the dtypes in the
   [schema doc](../data/schemas/papertrading.md), and upload them to the
   `papertrading` container.

> The agent loop needs a valid `CLAUDE_API_KEY` and `FINNHUB_API_KEY` to run.
> Without them, the read endpoints (`/portfolio`, `/trades`, …) still work once
> `/setup` has run.

## Frontend

```bash
cd frontend-prod
npm install
npm run dev          # stub data, no backend
```

To hit a backend during dev, set in `frontend-prod/.env`:
- `VITE_API_BASE=https://<func-host>/api` — the deployed API (cross-origin), or
- `VITE_API_PROXY=http://localhost:7071` — proxy `/api` to your local `func start`
  (avoids CORS).

See [../architecture/frontend.md](../architecture/frontend.md) for the stub vs
live behaviour.

## TODO

- [ ] Add a tiny `seed_from_samples.py` helper that uploads the sample CSVs as
      Parquet to a local/dev `papertrading` container.
