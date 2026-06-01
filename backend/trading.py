"""Shared paper-trading logic: validate a trade and reconcile it against
portfolio positions and the cash ledger. Used by both the /trade endpoint and
the autonomous agent."""

from datetime import datetime

import polars as pl

from storage.blobs import read_parquet, write_parquet

CONTAINER = "papertrading"


class TradeError(Exception):
    """Raised when a trade is invalid (bad input, insufficient cash, oversell)."""


def apply_trade(symbol, shares, price, side) -> dict:
    """Record a BUY/SELL and update positions + cash. Raises TradeError on invalid input."""
    if (
        not isinstance(symbol, str)
        or not isinstance(shares, (int, float))
        or not isinstance(price, (int, float))
        or not isinstance(side, str)
        or shares <= 0
        or price <= 0
        or side.upper() not in ("BUY", "SELL")
    ):
        raise TradeError("symbol (str), shares (>0), price (>0), side (BUY/SELL) required")

    symbol = symbol.upper()
    side = side.upper()
    shares = int(shares)
    price = float(price)
    cost = shares * price

    portfolio = read_parquet(CONTAINER, "portfolio.parquet")
    cash_ledger = read_parquet(CONTAINER, "cash_ledger.parquet")
    current_cash = float(cash_ledger.row(-1, named=True)["amount"]) if len(cash_ledger) > 0 else 0.0

    existing = portfolio.filter(pl.col("symbol") == symbol)
    held_shares = int(existing.row(0, named=True)["shares"]) if len(existing) > 0 else 0
    held_avg = float(existing.row(0, named=True)["avg_cost"]) if len(existing) > 0 else 0.0

    if side == "BUY":
        if cost > current_cash:
            raise TradeError(f"Insufficient cash: need {cost:.2f}, have {current_cash:.2f}")
        new_shares = held_shares + shares
        new_avg = (held_shares * held_avg + cost) / new_shares
        new_cash = current_cash - cost
    else:  # SELL
        if shares > held_shares:
            raise TradeError(f"Cannot sell {shares} of {symbol}: only {held_shares} held")
        new_shares = held_shares - shares
        new_avg = held_avg  # avg cost unchanged on sell
        new_cash = current_cash + cost

    # Rebuild the position row (drop if fully closed).
    portfolio = portfolio.filter(pl.col("symbol") != symbol)
    if new_shares > 0:
        updated = pl.DataFrame(
            {
                "symbol": [symbol],
                "shares": [new_shares],
                "avg_cost": [round(new_avg, 4)],
                "market_value": [round(new_shares * price, 2)],
            }
        )
        portfolio = pl.concat([portfolio, updated], how="diagonal_relaxed")
    write_parquet(CONTAINER, "portfolio.parquet", portfolio)

    new_trade = pl.DataFrame(
        {
            "date": [datetime.now().date()],
            "symbol": [symbol],
            "shares": [shares],
            "price": [price],
            "side": [side],
        }
    )
    trades = read_parquet(CONTAINER, "trades.parquet")
    write_parquet(CONTAINER, "trades.parquet", pl.concat([trades, new_trade], how="diagonal_relaxed"))

    cash_row = pl.DataFrame({"date": [datetime.now().date()], "amount": [round(new_cash, 2)]})
    write_parquet(CONTAINER, "cash_ledger.parquet", pl.concat([cash_ledger, cash_row], how="diagonal_relaxed"))

    return {"symbol": symbol, "shares": shares, "price": price, "side": side, "cash": round(new_cash, 2)}
