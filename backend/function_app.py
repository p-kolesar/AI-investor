import json
import logging
import time
from datetime import datetime, timezone

import polars as pl
import requests
import azure.functions as func

from market.finnhub import FinnhubClient
from storage.blobs import write_parquet, read_parquet
from trading import apply_trade, TradeError
from agent.loop import run_agent
from realestate.scraper import (
    BASE,
    UA,
    CONTAINER as RE_CONTAINER,
    _robots_allows,
    _parse,
    _write_csv,
    _coverage,
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

CONTAINER = "papertrading"
INITIAL_CASH = 100_000

HTTP_BUDGET_S = 150  # stop scraping here; guarantees we respond well under the 230s Functions limit

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


# ---- Real estate scraper ----


@app.route(route="scrape-realestate", methods=["GET"])
def scrape_realestate(req: func.HttpRequest) -> func.HttpResponse:
    """Scrape real-estate listings into a CSV blob.

    Query params: locality (comma-separated, default "bratislava-ruzinov"),
    deal ("predaj"), type ("byty"), pages (1-10). Stops at HTTP_BUDGET_S to stay
    under the Functions request timeout; `complete=false` flags an early stop.
    """
    t0 = time.time()
    localities = [s.strip() for s in req.params.get("locality", "bratislava-ruzinov").split(",") if s.strip()]
    deal = req.params.get("deal", "predaj")
    ptype = req.params.get("type", "byty")
    try:
        pages = max(1, min(int(req.params.get("pages", "1")), 10))
    except ValueError:
        pages = 1

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session = requests.Session()
    rows, complete = [], True
    try:
        for loc in localities:
            base_url = f"{BASE}/vysledky/{ptype}/{loc}/{deal}"
            if not _robots_allows(base_url):
                continue
            for n in range(1, pages + 1):
                if time.time() - t0 > HTTP_BUDGET_S:  # the timing guarantee
                    complete = False
                    break
                url = base_url if n == 1 else f"{base_url}?page={n}"
                try:
                    r = session.get(
                        url,
                        headers={"User-Agent": UA, "Accept-Language": "sk,en;q=0.8"},
                        timeout=15,
                    )
                    r.raise_for_status()
                except Exception as e:
                    logging.error("fetch %s: %s", url, e)
                    break
                for rec in _parse(r.text, base_url):
                    rec.update({"scraped_at": ts, "locality": loc, "deal": deal})
                    rows.append(rec)
                time.sleep(1.0)  # politeness between pages
            if not complete:
                break

        blob = _write_csv(rows, ts) if rows else None
        body = {
            "ok": bool(rows),
            "complete": complete,
            "blob": blob,
            "container": RE_CONTAINER,
            "coverage": _coverage(rows),
            "elapsed_s": round(time.time() - t0, 1),
        }
        return func.HttpResponse(
            json.dumps(body, ensure_ascii=False),
            mimetype="application/json",
            status_code=200 if rows else 502,
        )
    except Exception as e:
        logging.exception("scrape-realestate failed")
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}),
            mimetype="application/json",
            status_code=500,
        )


# ---- Health ----


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe."""
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json", status_code=200)
