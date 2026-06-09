"""Unit tests for agent.loop pure helpers + watchlist mutation.

These are the deterministic, side-effect-light parts of the agent. `run_agent`
itself (full orchestration over Claude + Finnhub) is left to a future
integration-style test — see tests/README.md.
"""

import json
from datetime import date
from types import SimpleNamespace

import polars as pl
import pytest

from agent import loop
from agent.loop import (
    _cost, _extract_json, _memo_after_json, _symbol_of,
    _apply_watchlist_changes, MAX_WATCHLIST,
)

CONTAINER = "papertrading"


# ---- _cost -----------------------------------------------------------------

def test_cost_input_and_output_rates():
    assert _cost(1_000_000, 0) == pytest.approx(3.00)     # $3 / 1M input
    assert _cost(0, 1_000_000) == pytest.approx(15.00)    # $15 / 1M output
    assert _cost(1_000, 1_000) == pytest.approx((1_000 * 3 + 1_000 * 15) / 1_000_000)


# ---- _extract_json ---------------------------------------------------------

def test_extract_json_from_fenced_block():
    assert _extract_json('prefix\n```json\n{"a": 1}\n```\nsuffix') == {"a": 1}


def test_extract_json_from_bare_object():
    assert _extract_json('noise {"b": 2} trailing') == {"b": 2}


def test_extract_json_returns_none_when_absent():
    assert _extract_json("no json here at all") is None


def test_extract_json_returns_none_on_malformed():
    assert _extract_json("{not: valid, json}") is None


# ---- _memo_after_json ------------------------------------------------------

def test_memo_after_json_strips_leading_trades_block():
    text = '```json\n{"trades": []}\n```\n\nInvestment memo prose here.'
    assert _memo_after_json(text) == "Investment memo prose here."


# ---- _symbol_of ------------------------------------------------------------

def test_symbol_of_handles_dict_and_string():
    assert _symbol_of({"symbol": "aapl"}) == "AAPL"
    assert _symbol_of("msft") == "MSFT"


# ---- _apply_watchlist_changes ---------------------------------------------

@pytest.fixture
def fc():
    """Fake Finnhub client: prices everything except 'BAD' (unpriceable)."""
    def get_quote(symbol):
        return {"price": None if symbol == "BAD" else 123.0}
    return SimpleNamespace(get_quote=get_quote)


@pytest.fixture(autouse=True)
def _no_write(monkeypatch):
    # _apply_watchlist_changes persists the watchlist; keep it in-memory.
    monkeypatch.setattr(loop, "write_parquet", lambda *a, **k: None)


def test_remove_unheld_symbol(fc):
    wl, changed = _apply_watchlist_changes(fc, ["AAPL", "MSFT"], add=[], remove=[{"symbol": "MSFT"}], held=[])
    assert wl == ["AAPL"] and changed is True


def test_cannot_remove_held_symbol(fc):
    wl, changed = _apply_watchlist_changes(fc, ["AAPL"], add=[], remove=[{"symbol": "AAPL"}], held=["AAPL"])
    assert wl == ["AAPL"] and changed is False


def test_add_valid_symbol(fc):
    wl, changed = _apply_watchlist_changes(fc, ["AAPL"], add=[{"symbol": "nvda"}], remove=[], held=[])
    assert "NVDA" in wl and changed is True


def test_add_rejects_unpriceable_symbol(fc):
    wl, changed = _apply_watchlist_changes(fc, ["AAPL"], add=[{"symbol": "BAD"}], remove=[], held=[])
    assert wl == ["AAPL"] and changed is False


def test_add_skips_existing_symbol(fc):
    wl, changed = _apply_watchlist_changes(fc, ["AAPL"], add=[{"symbol": "aapl"}], remove=[], held=[])
    assert wl == ["AAPL"] and changed is False


def test_add_respects_size_cap(fc):
    full = [f"S{i}" for i in range(MAX_WATCHLIST)]
    wl, changed = _apply_watchlist_changes(fc, full, add=[{"symbol": "NEW"}], remove=[], held=[])
    assert "NEW" not in wl and changed is False


# ---- _write_snapshot -------------------------------------------------------

def test_write_snapshot_marks_to_market_and_appends(blob_store, monkeypatch):
    blob_store.seed(CONTAINER, "portfolio.parquet", pl.DataFrame({
        "symbol": ["AAPL", "MSFT"], "shares": [10, 5],
        "avg_cost": [100.0, 200.0], "market_value": [900.0, 900.0]}))  # stale last-trade values
    blob_store.seed(CONTAINER, "cash_ledger.parquet",
                    pl.DataFrame({"date": [date.today()], "amount": [5000.0]}))
    blob_store.patch(monkeypatch, loop)  # overrides the autouse no-op write
    snap_fc = SimpleNamespace(get_quote=lambda s: {"price": 150.0 if s == "AAPL" else 250.0})

    loop._write_snapshot(snap_fc)

    row = blob_store.read_parquet(CONTAINER, "snapshots.parquet").row(-1, named=True)
    assert row["market_value"] == 2750.0          # live: 10*150 + 5*250, not the stale 1800
    assert row["cash"] == 5000.0
    assert row["total"] == 7750.0
    assert json.loads(row["positions"]) == [
        {"symbol": "AAPL", "shares": 10}, {"symbol": "MSFT", "shares": 5}]


def test_write_snapshot_falls_back_to_stored_value_when_unpriceable(blob_store, monkeypatch):
    blob_store.seed(CONTAINER, "portfolio.parquet", pl.DataFrame({
        "symbol": ["AAPL"], "shares": [10],
        "avg_cost": [100.0], "market_value": [1234.0]}))
    blob_store.seed(CONTAINER, "cash_ledger.parquet",
                    pl.DataFrame({"date": [date.today()], "amount": [0.0]}))
    blob_store.patch(monkeypatch, loop)
    snap_fc = SimpleNamespace(get_quote=lambda s: {"price": None})  # Finnhub can't price it

    loop._write_snapshot(snap_fc)

    row = blob_store.read_parquet(CONTAINER, "snapshots.parquet").row(-1, named=True)
    assert row["market_value"] == 1234.0          # fell back to stored last-trade value


def test_snapshot_portfolio_writes_without_agent(blob_store, monkeypatch):
    blob_store.seed(CONTAINER, "portfolio.parquet", pl.DataFrame({
        "symbol": ["AAPL"], "shares": [10],
        "avg_cost": [100.0], "market_value": [1000.0]}))
    blob_store.seed(CONTAINER, "cash_ledger.parquet",
                    pl.DataFrame({"date": [date.today()], "amount": [2000.0]}))
    blob_store.patch(monkeypatch, loop)
    # The on-demand path builds its own Finnhub client — no Claude involved.
    monkeypatch.setattr(loop, "FinnhubClient",
                        lambda: SimpleNamespace(get_quote=lambda s: {"price": 150.0}))

    result = loop.snapshot_portfolio()

    assert result["market_value"] == 1500.0       # 10 * 150
    assert result["total"] == 3500.0              # 1500 + 2000 cash
    assert result["positions"] == [{"symbol": "AAPL", "shares": 10}]
    assert len(blob_store.read_parquet(CONTAINER, "snapshots.parquet")) == 1
