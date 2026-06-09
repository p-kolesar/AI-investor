import json
import logging
from datetime import datetime

import polars as pl
import azure.functions as func

from market.finnhub import FinnhubClient
from storage.blobs import write_parquet, read_parquet
from trading import apply_trade, TradeError
from agent.loop import run_agent, snapshot_portfolio


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

        # Watchlist — sector-diversified seed; the agent grows/prunes it from here.
        watchlist = pl.DataFrame(
            {
                "symbol": [
                    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
                    "JPM", "BRK.B", "UNH", "LLY", "XOM",
                    "CAT", "PG", "SPY", "QQQ",
                ],
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

        # Daily snapshots — append-only, one row per agent run (live-marked).
        snapshots = pl.DataFrame(
            {
                "timestamp": pl.Series([], dtype=pl.Datetime),
                "positions": pl.Series([], dtype=pl.Utf8),
                "market_value": pl.Series([], dtype=pl.Float64),
                "cash": pl.Series([], dtype=pl.Float64),
                "total": pl.Series([], dtype=pl.Float64),
            }
        )
        write_parquet(CONTAINER, "snapshots.parquet", snapshots)

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
        result = apply_trade(body.get("symbol"), body.get("shares"), body.get("price"), body.get("side"))
        return func.HttpResponse(
            json.dumps({"status": "recorded", "trade": result}, default=str),
            mimetype="application/json",
            status_code=201,
        )
    except TradeError as e:
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=400, mimetype="application/json")
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


# ---- Daily snapshots ----


@app.route(route="snapshots", methods=["GET"])
def get_snapshots(req: func.HttpRequest) -> func.HttpResponse:
    """Timestamped portfolio+cash snapshots, most recent first. ?limit=N (default 60).

    Each row: {timestamp, positions:[{symbol,shares}], market_value, cash, total}.
    Backs the frontend "Daily" tab."""
    try:
        try:
            limit = max(1, int(req.params.get("limit", "60")))
        except ValueError:
            limit = 60
        snaps = read_parquet(CONTAINER, "snapshots.parquet")
        rows = snaps.tail(limit).reverse().to_dicts() if len(snaps) > 0 else []
        for r in rows:
            r["positions"] = json.loads(r["positions"]) if r.get("positions") else []
        return func.HttpResponse(json.dumps(rows, default=str), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Snapshots fetch failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


@app.route(route="snapshot", methods=["GET"])
def write_snapshot(req: func.HttpRequest) -> func.HttpResponse:
    """Append a live-marked snapshot of the *current* portfolio + cash on demand —
    no agent run, no Claude calls, no trades. Returns the written row."""
    try:
        result = snapshot_portfolio()
        return func.HttpResponse(json.dumps(result, default=str), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Snapshot write failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Agent log ----


@app.route(route="agent/log", methods=["GET"])
def get_agent_log(req: func.HttpRequest) -> func.HttpResponse:
    """Recent agent runs (date, tokens, cost, memo) + cumulative spend. ?limit=N (default 10)."""
    try:
        try:
            limit = max(1, int(req.params.get("limit", "10")))
        except ValueError:
            limit = 10
        log = read_parquet(CONTAINER, "agent_log.parquet")
        cumulative = float(log["estimated_cost_usd"].sum()) if len(log) > 0 else 0.0
        recent = log.tail(limit).reverse().to_dicts() if len(log) > 0 else []
        return func.HttpResponse(
            json.dumps(
                {"runs": recent, "total_runs": len(log), "cumulative_cost_usd": round(cumulative, 4)},
                default=str,
            ),
            mimetype="application/json",
            status_code=200,
        )
    except Exception as e:
        logging.error(f"Agent log fetch failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Watchlist ----


@app.route(route="watchlist", methods=["GET"])
def get_watchlist(req: func.HttpRequest) -> func.HttpResponse:
    """Get the current (agent-managed) watchlist."""
    try:
        symbols = read_parquet(CONTAINER, "watchlist.parquet")["symbol"].to_list()
        return func.HttpResponse(
            json.dumps({"watchlist": symbols, "count": len(symbols)}),
            mimetype="application/json",
            status_code=200,
        )
    except Exception as e:
        logging.error(f"Watchlist fetch failed: {e}")
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
    """Trigger the autonomous agent: screening -> deep dive -> trades + memo."""
    try:
        result = run_agent()
        return func.HttpResponse(json.dumps(result, default=str), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Agent run failed: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")


# ---- Agent: Daily timer trigger ----


# NCRONTAB is {second} {minute} {hour} {day} {month} {day-of-week}. The hour is
# interpreted in the app's WEBSITE_TIME_ZONE; set that app setting to
# "Central European Standard Time" (Windows) / "Europe/Bratislava" (Linux) so
# 07:55 fires at 07:55 CET/CEST. Without it, Azure uses UTC.
@app.timer_trigger(arg_name="timer", schedule="0 55 7 * * *", run_on_startup=False, use_monitor=True)
def daily_agent_timer(timer: func.TimerRequest) -> None:
    """Run the autonomous agent every weekday at 07:55 CET; skip Sat/Sun.

    Same inner call as POST /api/agent/run, just driven by the timer instead of HTTP.
    """
    now = datetime.now()
    if now.weekday() >= 5:  # Mon=0 .. Sat=5, Sun=6
        logging.info("Weekend (%s) — skipping daily agent run.", now.strftime("%A"))
        return
    try:
        result = run_agent()
        logging.info("Daily agent run complete: %s", json.dumps(result, default=str))
    except Exception:
        logging.exception("Daily agent run failed")
        raise



# ---- Health ----


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe."""
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json", status_code=200)
