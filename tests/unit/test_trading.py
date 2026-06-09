"""Unit tests for trading.apply_trade — the core paper-trade money logic.

Covers the data-contract invariants documented in docs/data/: BUY/SELL
reconciliation, weighted-average cost, avg_cost unchanged on SELL, position
dropped at zero shares, append-only trade ledger + cash ledger, and validation.
"""

import polars as pl
import pytest

import trading
from trading import apply_trade, TradeError

CONTAINER = "papertrading"


@pytest.fixture
def store(blob_store, monkeypatch):
    """Patched in-memory storage seeded with $100K cash and empty positions."""
    blob_store.patch(monkeypatch, trading)
    blob_store.seed_papertrading(cash=100_000.0)
    return blob_store


def _cash(store):
    return store.read_parquet(CONTAINER, "cash_ledger.parquet").row(-1, named=True)["amount"]


def _portfolio(store):
    return store.read_parquet(CONTAINER, "portfolio.parquet")


def _trades(store):
    return store.read_parquet(CONTAINER, "trades.parquet")


# ---- BUY -------------------------------------------------------------------

def test_buy_creates_position_and_debits_cash(store):
    result = apply_trade("AAPL", 10, 200.0, "BUY")

    assert result == {"symbol": "AAPL", "shares": 10, "price": 200.0, "side": "BUY", "cash": 98_000.0}
    pf = _portfolio(store)
    assert pf.height == 1
    row = pf.row(0, named=True)
    assert row["symbol"] == "AAPL"
    assert row["shares"] == 10
    assert row["avg_cost"] == pytest.approx(200.0)
    assert row["market_value"] == pytest.approx(2_000.0)
    assert _cash(store) == pytest.approx(98_000.0)


def test_buy_insufficient_cash_raises(store):
    with pytest.raises(TradeError, match="Insufficient cash"):
        apply_trade("AAPL", 1_000, 200.0, "BUY")  # 200,000 > 100,000


def test_buy_adds_to_existing_with_weighted_average(store):
    apply_trade("AAPL", 60, 212.34, "BUY")
    apply_trade("AAPL", 10, 228.00, "BUY")

    row = _portfolio(store).row(0, named=True)
    assert row["shares"] == 70
    # (60*212.34 + 10*228) / 70
    assert row["avg_cost"] == pytest.approx(214.5771, abs=1e-3)
    assert row["market_value"] == pytest.approx(70 * 228.0)
    assert _cash(store) == pytest.approx(100_000.0 - 60 * 212.34 - 10 * 228.0)


# ---- SELL ------------------------------------------------------------------

def test_sell_reduces_shares_and_credits_cash(store):
    apply_trade("AAPL", 10, 200.0, "BUY")
    result = apply_trade("AAPL", 4, 210.0, "SELL")

    assert result["cash"] == pytest.approx(98_000.0 + 4 * 210.0)
    row = _portfolio(store).row(0, named=True)
    assert row["shares"] == 6
    assert row["market_value"] == pytest.approx(6 * 210.0)


def test_sell_leaves_avg_cost_unchanged(store):
    apply_trade("AAPL", 10, 200.0, "BUY")
    apply_trade("AAPL", 5, 999.0, "SELL")  # high sell price must not move avg_cost

    assert _portfolio(store).row(0, named=True)["avg_cost"] == pytest.approx(200.0)


def test_sell_more_than_held_raises(store):
    apply_trade("AAPL", 5, 200.0, "BUY")
    with pytest.raises(TradeError, match="only 5 held"):
        apply_trade("AAPL", 10, 200.0, "SELL")


def test_sell_all_closes_position(store):
    apply_trade("AAPL", 10, 200.0, "BUY")
    apply_trade("AAPL", 10, 210.0, "SELL")

    pf = _portfolio(store)
    assert pf.filter(pl.col("symbol") == "AAPL").height == 0  # row dropped at 0 shares


# ---- Ledgers (append-only) -------------------------------------------------

def test_trade_appended_to_ledger(store):
    apply_trade("AAPL", 10, 200.0, "BUY")
    apply_trade("MSFT", 5, 400.0, "BUY")

    trades = _trades(store)
    assert trades.height == 2
    assert trades["symbol"].to_list() == ["AAPL", "MSFT"]
    assert trades["side"].to_list() == ["BUY", "BUY"]


def test_cash_ledger_appends_a_row_per_trade(store):
    start_rows = store.read_parquet(CONTAINER, "cash_ledger.parquet").height
    apply_trade("AAPL", 10, 200.0, "BUY")
    apply_trade("AAPL", 2, 210.0, "SELL")

    assert store.read_parquet(CONTAINER, "cash_ledger.parquet").height == start_rows + 2


# ---- Normalization & validation -------------------------------------------

def test_symbol_and_side_are_normalized_uppercase(store):
    result = apply_trade("aapl", 10, 200.0, "buy")
    assert result["symbol"] == "AAPL"
    assert result["side"] == "BUY"
    assert _portfolio(store).row(0, named=True)["symbol"] == "AAPL"


@pytest.mark.parametrize("symbol,shares,price,side", [
    ("AAPL", 0, 200.0, "BUY"),      # shares must be > 0
    ("AAPL", -5, 200.0, "BUY"),     # negative shares
    ("AAPL", 10, 0.0, "BUY"),       # price must be > 0
    ("AAPL", 10, 200.0, "HOLD"),    # side must be BUY/SELL
    ("AAPL", "ten", 200.0, "BUY"),  # shares not numeric
    (123, 10, 200.0, "BUY"),        # symbol not a string
])
def test_invalid_inputs_raise(store, symbol, shares, price, side):
    with pytest.raises(TradeError):
        apply_trade(symbol, shares, price, side)
