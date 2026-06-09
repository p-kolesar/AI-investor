# Storage account, container & auth

Status: **current** · Last verified: 2026-06-09

## Account

The app uses the Function App's storage account, referenced by the
`AzureWebJobsStorage` app setting. There is no separate database — the Parquet
blobs are the database. Provisioned by [`infra/main.bicep`](../../infra/main.bicep).

## Container

| Container | Created by | Notes |
| --- | --- | --- |
| `papertrading` | assumed to exist / created out of band; populated by `GET /api/setup` | Holds all Parquet state blobs. |

## Authentication (storage)

`storage/blobs.py` connects with
`BlobServiceClient.from_connection_string(AzureWebJobsStorage)`, so
`AzureWebJobsStorage` must be a **full connection string**.

> ⚠️ On Flex Consumption the platform can use *identity-based*
> `AzureWebJobsStorage` (`AzureWebJobsStorage__accountName` + managed identity)
> instead of a connection string. The connection-string path above would not
> work in that mode — keep this in mind if you change storage auth.

## Blob naming & formats

All blobs are Parquet (Polars `write_parquet`):

`portfolio.parquet`, `trades.parquet`, `watchlist.parquet`,
`agent_log.parquet`, `prices_cache.parquet`, `cash_ledger.parquet`,
`benchmark.parquet`, `finnhub_usage.parquet`.

## Local emulation

For local dev, point `AzureWebJobsStorage` at Azurite or a real dev storage
account, then call `GET /api/setup` to materialize the Parquet blobs. The
[samples/](samples/) CSVs can be converted to Parquet to seed realistic state.
