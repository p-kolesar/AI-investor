import json
import logging
from datetime import datetime

import polars as pl
import azure.functions as func

from market.finnhub import FinnhubClient
from storage.blobs import write_parquet, read_parquet

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

CONTAINER = "papertrading"
INITIAL_CASH = 100_000

# ---- Admin: Initialize portfolio ----


@app.route(route="setup", methods=["GET"])
def admin_init(req: func.HttpRequest) -> func.HttpResponse:
    """Initialize portfolio with empty Parquet files and $100K cash."""
    try:
        # Portfolio: positions + cash
        portfolio = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.Utf8),
                "shares": pl.Series([], dtype=pl.Int64),
                "avg_cost": pl.Series([], dtype=pl.Float64),
                "market_value": pl.Series([], dtype=pl.Float64),
            }
        )
        write_parquet(CONTAINER, "portfolio.parquet", portfolio)

        # Trades: append-only ledger
        trades = pl.DataFrame(
            {
                "date": pl.Series([], dtype=pl.Date),
                "symbol": pl.Series([], dtype=pl.Utf8),
                "shares": pl.Series([], dtype=pl.Int64),
                "price": pl.Series([], dtype=pl.Float64),
                "side": pl.Series([], dtype=pl.Utf8),
            }
        )
        write_parquet(CONTAINER, "trades.parquet", trades)

        # Watchlist
        watchlist = pl.DataFrame(
            {
                "symbol": ["AAPL", "MSFT", "NVDA", "JPM", "AMZN", "GOOGL", "META", "BRK.B", "SPY", "QQQ"],
            }
        )
        write_parquet(CONTAINER, "watchlist.parquet", watchlist)

        # Agent log
        agent_log = pl.DataFrame(
            {
                "run_date": pl.Series([], dtype=pl.Date),
                "level1_input_tokens": pl.Series([], dtype=pl.Int64),
                "level1_output_tokens": pl.Series([], dtype=pl.Int64),
                "level2_input_tokens": pl.Series([], dtype=pl.Int64),
                "level2_output_tokens": pl.Series([], dtype=pl.Int64),
                "total_tokens": pl.Series([], dtype=pl.Int64),
                "estimated_cost_usd": pl.Series([], dtype=pl.Float64),
                "memo": pl.Series([], dtype=pl.Utf8),
            }
        )
        write_parquet(CONTAINER, "agent_log.parquet", agent_log)

        # Prices cache (Finnhub /quote has no volume field, so it is not stored)
        prices_cache = pl.DataFrame(
            {
                "symbol": pl.Series([], dtype=pl.Utf8),
                "price": pl.Series([], dtype=pl.Float64),
                "open": pl.Series([], dtype=pl.Float64),
                "high": pl.Series([], dtype=pl.Float64),
                "low": pl.Series([], dtype=pl.Float64),
                "timestamp": pl.Series([], dtype=pl.Datetime),
            }
        )
        write_parquet(CONTAINER, "prices_cache.parquet", prices_cache)

        # Benchmark (SPY daily close) — stub
        benchmark = pl.DataFrame(
            {
                "date": pl.Series([], dtype=pl.Date),
                "close": pl.Series([], dtype=pl.Float64),
            }
        )
        write_parquet(CONTAINER, "benchmark.parquet", benchmark)

        # Cash ledger (latest row = current cash balance)
        cash_ledger = pl.DataFrame(
            {
                "date": [datetime.now().date()],
                "amount": [float(INITIAL_CASH)],
            }
        )
        write_parquet(CONTAINER, "cash_ledger.parquet", cash_ledger)

        return func.HttpResponse(
            json.dumps({"status": "initialized", "cash": INITIAL_CASH}),
            mimetype="application/json",
            status_code=200,
        )
    except Exception as e:
        logging.error(f"Init failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Portfolio ----


@app.route(route="portfolio", methods=["GET"])
def get_portfolio(req: func.HttpRequest) -> func.HttpResponse:
    """Get current portfolio positions + cash."""
    try:
        portfolio = read_parquet(CONTAINER, "portfolio.parquet")
        cash_ledger = read_parquet(CONTAINER, "cash_ledger.parquet")
        current_cash = cash_ledger.row(-1, named=True)["amount"] if len(cash_ledger) > 0 else 0

        result = {
            "positions": portfolio.to_dicts(),
            "cash": current_cash,
            "total_value": float(portfolio["market_value"].sum()) + current_cash,
        }
        return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Portfolio fetch failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Trade: Record a trade ----


@app.route(route="trade", methods=["POST"])
def record_trade(req: func.HttpRequest) -> func.HttpResponse:
    """Record a BUY or SELL trade and reconcile positions + cash."""
    try:
        body = req.get_json()
        symbol = body.get("symbol")
        shares = body.get("shares")
        price = body.get("price")
        side = body.get("side")

        # Validate before any attribute access (None.upper() would 500 otherwise).
        if (
            not isinstance(symbol, str)
            or not isinstance(shares, (int, float))
            or not isinstance(price, (int, float))
            or not isinstance(side, str)
            or shares <= 0
            or price <= 0
            or side.upper() not in ("BUY", "SELL")
        ):
            return func.HttpResponse(
                json.dumps({"error": "Invalid trade: symbol (str), shares (>0), price (>0), side (BUY/SELL) required"}),
                status_code=400,
                mimetype="application/json",
            )

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
                return func.HttpResponse(
                    json.dumps({"error": f"Insufficient cash: need {cost:.2f}, have {current_cash:.2f}"}),
                    status_code=400,
                    mimetype="application/json",
                )
            new_shares = held_shares + shares
            new_avg = (held_shares * held_avg + cost) / new_shares
            new_cash = current_cash - cost
        else:  # SELL
            if shares > held_shares:
                return func.HttpResponse(
                    json.dumps({"error": f"Cannot sell {shares} of {symbol}: only {held_shares} held"}),
                    status_code=400,
                    mimetype="application/json",
                )
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

        # Append to the trade ledger.
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

        # Append the new running cash balance.
        cash_row = pl.DataFrame({"date": [datetime.now().date()], "amount": [round(new_cash, 2)]})
        write_parquet(CONTAINER, "cash_ledger.parquet", pl.concat([cash_ledger, cash_row], how="diagonal_relaxed"))

        return func.HttpResponse(
            json.dumps(
                {"status": "recorded", "trade": new_trade.to_dicts()[0], "cash": round(new_cash, 2)},
                default=str,
            ),
            mimetype="application/json",
            status_code=201,
        )
    except Exception as e:
        logging.error(f"Trade record failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Trades: Get all trades ----


@app.route(route="trades", methods=["GET"])
def get_trades(req: func.HttpRequest) -> func.HttpResponse:
    """Get all trades (append-only ledger)."""
    try:
        trades = read_parquet(CONTAINER, "trades.parquet")
        return func.HttpResponse(json.dumps(trades.to_dicts(), default=str), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Trades fetch failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Prices: Get quote with cache ----


@app.route(route="prices/{symbol}", methods=["GET"])
def get_price(req: func.HttpRequest) -> func.HttpResponse:
    """Get live quote for a symbol (15-min cache via Finnhub)."""
    try:
        symbol = req.route_params.get("symbol").upper()
        client = FinnhubClient()
        quote = client.get_quote(symbol)
        return func.HttpResponse(json.dumps(quote, default=str), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Price fetch failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Agent: Run (stub for Phase 2) ----


@app.route(route="agent/run", methods=["POST"])
def agent_run(req: func.HttpRequest) -> func.HttpResponse:
    """Trigger agent loop (Phase 2: screening + deep dive + trade decision)."""
    return func.HttpResponse(
        json.dumps({"status": "stub", "message": "Agent loop in Phase 2"}),
        mimetype="application/json",
        status_code=200,
    )


# ---- Health ----


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe."""
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json", status_code=200)
