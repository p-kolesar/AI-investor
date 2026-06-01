"""Finnhub API wrapper with rate limiting and caching."""

import os
import time
from datetime import datetime, timedelta

import polars as pl
import requests

from storage.blobs import read_parquet, write_parquet


FINNHUB_BASE = "https://finnhub.io/api/v1"
CACHE_CONTAINER = "papertrading"
CACHE_FILE = "prices_cache.parquet"
USAGE_FILE = "finnhub_usage.parquet"
CACHE_TTL_MINUTES = 15

# Cost guardrails. Free tier is 60 calls/min; we throttle to ~70% of it.
# DAILY_CALL_CAP is our own safety net (Finnhub free has no daily cap).
RATE_LIMIT_PER_MIN = 42
DAILY_CALL_CAP = 200


class FinnhubClient:
    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError("FINNHUB_API_KEY not set")
        # Sliding window of recent call timestamps for the per-minute throttle.
        # Per-instance only (resets on cold start) — best-effort burst protection;
        # the hard daily cap below is persisted in Blob and survives restarts.
        self._call_times: list[float] = []

    # ---- Rate limiting -----------------------------------------------------

    def _throttle_per_minute(self) -> None:
        """Block until fewer than RATE_LIMIT_PER_MIN calls occurred in the last 60s."""
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= RATE_LIMIT_PER_MIN:
            sleep_for = 60 - (now - self._call_times[0])
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.time()
            self._call_times = [t for t in self._call_times if now - t < 60]
        self._call_times.append(time.time())

    def _enforce_daily_cap(self) -> None:
        """Read/increment the persisted daily call counter; raise if the cap is hit."""
        today = datetime.now().date()
        try:
            usage = read_parquet(CACHE_CONTAINER, USAGE_FILE)
        except Exception:
            usage = pl.DataFrame(
                {
                    "date": pl.Series([], dtype=pl.Date),
                    "calls": pl.Series([], dtype=pl.Int64),
                }
            )

        todays = usage.filter(pl.col("date") == today)
        count = int(todays.row(0, named=True)["calls"]) if len(todays) > 0 else 0
        if count >= DAILY_CALL_CAP:
            raise RuntimeError(f"Finnhub daily call cap reached ({DAILY_CALL_CAP}/day)")

        usage = usage.filter(pl.col("date") != today)
        usage = pl.concat(
            [usage, pl.DataFrame({"date": [today], "calls": [count + 1]})],
            how="diagonal_relaxed",
        )
        write_parquet(CACHE_CONTAINER, USAGE_FILE, usage)

    def _get(self, endpoint: str, params: dict) -> dict | list:
        """Make a rate-limited GET request to Finnhub."""
        self._throttle_per_minute()
        self._enforce_daily_cap()
        params["token"] = self.api_key
        resp = requests.get(f"{FINNHUB_BASE}{endpoint}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ---- Market data -------------------------------------------------------

    def get_quote(self, symbol: str) -> dict:
        """Get live quote (price, open, high, low) with 15-min cache."""
        cache = self._load_cache()

        cached = cache.filter(
            (pl.col("symbol") == symbol)
            & (pl.col("timestamp") > datetime.now() - timedelta(minutes=CACHE_TTL_MINUTES))
        )
        if len(cached) > 0:
            row = cached.row(0, named=True)
            return {
                "symbol": row["symbol"],
                "price": row["price"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "cached": True,
            }

        data = self._get("/quote", {"symbol": symbol})
        quote = {
            "symbol": symbol,
            "price": data.get("c"),
            "open": data.get("o"),
            "high": data.get("h"),
            "low": data.get("l"),
            "timestamp": datetime.now(),
        }

        self._save_cache(cache, quote)
        quote["cached"] = False
        return quote

    def get_fundamentals(self, symbol: str) -> dict:
        """Get P/E, EPS, ROE, dividend yield."""
        data = self._get("/stock/metric", {"symbol": symbol, "metric": "all"})
        metrics = data.get("metric", {}) if isinstance(data, dict) else {}
        return {
            "pe": metrics.get("peNormalizedAnnual"),
            "eps": metrics.get("epsNormalizedAnnual"),
            "roe": metrics.get("roeRfy"),
            "dividend_yield": metrics.get("dividendYieldIndicatedAnnual"),
        }

    def get_news(self, symbol: str, limit: int = 3) -> list:
        """Get latest news for a symbol (last 7 days)."""
        data = self._get(
            "/company-news",
            {
                "symbol": symbol,
                "from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "to": datetime.now().strftime("%Y-%m-%d"),
            },
        )
        items = data if isinstance(data, list) else []
        return [{"headline": item.get("headline"), "source": item.get("source")} for item in items[:limit]]

    def get_insider_sentiment(self, symbol: str) -> dict:
        """Get MSPR (insider sentiment indicator), latest period."""
        data = self._get("/stock/insider-sentiment", {"symbol": symbol})
        rows = data.get("data") if isinstance(data, dict) else None
        latest = rows[0] if rows else {}
        return {
            "change": latest.get("change"),
            "mspr": latest.get("mspr"),
        }

    def get_analyst_recommendation(self, symbol: str) -> dict:
        """Get latest analyst consensus (buy/hold/sell counts)."""
        data = self._get("/stock/recommendation", {"symbol": symbol})
        if isinstance(data, list) and data:
            latest = data[0]
            return {
                "period": latest.get("period"),
                "strong_buy": latest.get("strongBuy"),
                "buy": latest.get("buy"),
                "hold": latest.get("hold"),
                "sell": latest.get("sell"),
                "strong_sell": latest.get("strongSell"),
            }
        return {"period": None, "strong_buy": None, "buy": None, "hold": None, "sell": None, "strong_sell": None}

    def get_earnings(self, symbol: str) -> dict:
        """Get the next upcoming earnings date (for the earnings-risk rule)."""
        data = self._get(
            "/calendar/earnings",
            {
                "symbol": symbol,
                "from": datetime.now().strftime("%Y-%m-%d"),
                "to": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            },
        )
        rows = data.get("earningsCalendar") if isinstance(data, dict) else None
        next_date = rows[0].get("date") if rows else None
        return {"next_earnings_date": next_date}

    def get_price_target(self, symbol: str) -> dict:
        """Get analyst price target (high/low/mean/median)."""
        data = self._get("/stock/price-target", {"symbol": symbol})
        data = data if isinstance(data, dict) else {}
        return {
            "target_high": data.get("targetHigh"),
            "target_low": data.get("targetLow"),
            "target_mean": data.get("targetMean"),
            "target_median": data.get("targetMedian"),
        }

    # ---- Price cache -------------------------------------------------------

    def _load_cache(self) -> pl.DataFrame:
        """Load price cache or return an empty, correctly-typed DataFrame."""
        try:
            return read_parquet(CACHE_CONTAINER, CACHE_FILE)
        except Exception:
            return pl.DataFrame(
                {
                    "symbol": pl.Series([], dtype=pl.Utf8),
                    "price": pl.Series([], dtype=pl.Float64),
                    "open": pl.Series([], dtype=pl.Float64),
                    "high": pl.Series([], dtype=pl.Float64),
                    "low": pl.Series([], dtype=pl.Float64),
                    "timestamp": pl.Series([], dtype=pl.Datetime),
                }
            )

    def _save_cache(self, cache: pl.DataFrame, quote: dict) -> None:
        """Replace any prior row for this symbol, then append the fresh quote."""
        cache = cache.filter(pl.col("symbol") != quote["symbol"])
        new_row = pl.DataFrame([quote])
        combined = pl.concat([cache, new_row], how="diagonal_relaxed")
        write_parquet(CACHE_CONTAINER, CACHE_FILE, combined)
