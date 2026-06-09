# Architecture Decision Records (ADRs)

Status: **current** · Last verified: 2026-06-09

Short records of *why* a non-obvious choice was made, so future readers (human
or agent) don't undo it by accident. One file per decision, numbered.

## How to add one

Copy [0001-record-architecture-decisions.md](0001-record-architecture-decisions.md)
to the next number, fill in Context / Decision / Consequences, and link it here.

## Index

| # | Title | Status |
| --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-parquet-in-blob-as-datastore.md) | Parquet-in-Blob as the datastore (no relational DB) | Accepted |
| [0003](0003-trades-executed-deterministically.md) | Trades executed deterministically, not as a Claude tool | Accepted |
| [0004](0004-cost-guardrails.md) | Cost guardrails (token cap + spend cap) | Accepted |
| [0005](0005-append-only-ledgers.md) | Append-only ledgers; cash is the ledger's last row | Accepted |
