# Tests

Status: **current** · Last verified: 2026-06-09

Unit tests for the backend's key modules. They run **fully offline** — no Azure
Blob Storage, no Finnhub, no Claude. See [docs/](../docs/) for what the code does;
this folder verifies it still does it.

## Layout

```
pytest.ini              # (repo root) pythonpath=backend, testpaths=tests
tests/
  conftest.py           # FakeBlobStore fixture — in-memory stand-in for storage/blobs
  requirements.txt      # test-only deps (pytest, pytest-mock)
  unit/
    test_trading.py     # apply_trade — BUY/SELL reconciliation, the money logic
    test_finnhub.py     # rate limit, persisted daily cap, 15-min cache, parsers
    test_agent_loop.py  # pure helpers (_cost/_extract_json/…) + watchlist mutation
    test_tools.py       # tool schema + dispatcher
    test_prompts.py     # prompt builders (inputs + required JSON markers)
    test_blobs.py       # append_parquet union / new-blob behaviour
```

## Running

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate        # if not already
pip install -r ../tests/requirements.txt              # pytest, pytest-mock
cd ..
python -m pytest                                      # uses pytest.ini
python -m pytest tests/unit/test_trading.py -v        # one file, verbose
```

Or with the project venv directly:
`backend/.venv/Scripts/python.exe -m pytest`

## Conventions / how it works

- **No real I/O.** The backend persists state as Parquet blobs via
  `storage/blobs.py` (`read_parquet`/`write_parquet`). Modules import those names
  into their own namespace, so tests patch e.g. `trading.read_parquet` to point at
  the in-memory `FakeBlobStore` (see `conftest.py`). External clients (`_get` on
  the Finnhub client, the Anthropic client) are stubbed per-test.
- **Seed realistic state** with `blob_store.seed_papertrading()` — empty,
  correctly-typed portfolio/trades blobs + a one-row cash ledger (mirrors
  `GET /api/setup`). Schemas come from
  [docs/data/schemas/papertrading.md](../docs/data/schemas/papertrading.md).
- **One behaviour per test**, named `test_<unit>_<expectation>`.

## Not yet covered (future phases)

- `agent/loop.run_agent` end-to-end orchestration (needs stubbed Anthropic +
  Finnhub + storage; integration-style).
- `function_app.py` HTTP handlers (need `func.HttpRequest` mocks; they mostly
  delegate to the tested modules).
- `storage/blobs.read/write` against Azurite (integration, not unit).
