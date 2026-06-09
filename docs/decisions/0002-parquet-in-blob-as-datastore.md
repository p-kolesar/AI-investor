# 2. Parquet-in-Blob as the datastore (no relational DB)

Date: 2026-06-09 (documenting an earlier decision)
Status: Accepted

## Context

The app needs to persist portfolio state, a trade ledger, agent run history, and
caches. It runs on a Flex Consumption Function App with a storage account already
attached. The workload is tiny (hundreds of rows), read-mostly, single-writer,
and is a demo with a strict cost budget.

## Decision

Store all state as **Polars-written Parquet blobs in the `papertrading` container**
of the Function App's storage account. No relational database, no separate
service. Schemas are fixed by `GET /api/setup`; reads/writes go through
[`storage/blobs.py`](../../backend/storage/blobs.py).

## Consequences

- **Zero extra infra/cost** — reuses `AzureWebJobsStorage`; nothing to provision
  or pay for beyond the storage account.
- **Schema-on-write, no migrations** — changing a column means updating `/setup`
  + every writer and manually migrating existing blobs. This is the project's main
  footgun; the [data contract](../data/README.md) exists to manage it.
- **No concurrency control** — writers read-modify-write whole blobs. Fine for a
  single daily agent + occasional manual trade; would not survive real concurrency.
- **Typed, columnar, cheap to read** with Polars; easy to mirror to CSV for docs.
