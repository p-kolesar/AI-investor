# Testing

Status: **current** · Last verified: 2026-06-09

Unit tests for the key backend modules live in [`tests/`](../../tests/) and run
**fully offline** — no Azure Blob Storage, Finnhub, or Claude. The detailed
reference (layout, conventions, how the in-memory storage fake works) is
[tests/README.md](../../tests/README.md); this page is the docs-side pointer.

## Run them

```bash
# from the repo root, using the project venv (no activation needed)
backend/.venv/Scripts/python.exe -m pytest          # all tests (config in pytest.ini)
backend/.venv/Scripts/python.exe -m pytest -v       # verbose, one line per test
backend/.venv/Scripts/python.exe -m pytest tests/unit/test_trading.py -v
```

Test-only deps are in [tests/requirements.txt](../../tests/requirements.txt)
(`pytest`, `pytest-mock`) — kept out of the runtime `backend/requirements.txt`.

## What's covered

| Area | File | Notes |
| --- | --- | --- |
| Paper-trade money logic | `test_trading.py` | `apply_trade` BUY/SELL, weighted-avg, avg-unchanged-on-sell, oversell/cash guards, append-only ledgers. |
| Market data | `test_finnhub.py` | 15-min cache, persisted daily call cap, per-minute throttle, response parsers. |
| Agent helpers | `test_agent_loop.py` | `_cost`, `_extract_json`, `_memo_after_json`, watchlist add/remove/cap. |
| Tools / prompts | `test_tools.py`, `test_prompts.py` | tool schema + dispatch; prompt JSON-contract markers. |
| Storage | `test_blobs.py` | `append_parquet` union / new-blob behaviour. |

**Not yet covered** (integration-style, needs heavier mocking): `run_agent`
end-to-end orchestration and the `function_app.py` HTTP handlers.

## Adding a test

Backend modules persist via `storage/blobs.py`. Don't hit Azure — use the
`blob_store` fixture (an in-memory `FakeBlobStore`) and patch the
`read_parquet`/`write_parquet` names the module imported. Seed realistic state
with `blob_store.seed_papertrading()`. Stub external clients (the Finnhub `_get`,
the Anthropic client) per test. The data shapes you seed against are documented in
[../data/schemas/papertrading.md](../data/schemas/papertrading.md). See
[adding-a-feature.md](adding-a-feature.md) for the full change-with-tests flow.
