"""Unit tests for agent.loop pure helpers + watchlist mutation.

These are the deterministic, side-effect-light parts of the agent. `run_agent`
itself (full orchestration over Claude + Finnhub) is left to a future
integration-style test — see tests/README.md.
"""

from types import SimpleNamespace

import pytest

from agent import loop
from agent.loop import (
    _cost, _extract_json, _memo_after_json, _symbol_of,
    _apply_watchlist_changes, MAX_WATCHLIST,
)


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
