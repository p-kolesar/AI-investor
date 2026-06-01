"""Finnhub API wrapper with rate limiting and caching."""

import os
import time
from datetime import datetime, timedelta
from typing import Any

import polars as pl
import requests

from storage.blobs import read_parquet, write_parquet


FINNHUB_BASE = "https://finnhub.io/api/v1"
CACHE_CONTAINER = "papertrading"
CACHE_FILE = "prices_cache.parquet"
CACHE_TTL_MINUTES = 15


class FinnhubClient:
    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError("FINNHUB_API_KEY not set")
        self.call_count_today = 0
        self.last_rate_check = time.time()

    def _get(self, endpoint: str, params: dict) -> dict:
        """Make a rate-limited GET request to Finnhub."""
        params["token"] = self.api_key
        resp = requests.get(f"{FINNHUB_BASE}{endpoint}", params=params, timeout=10)
        resp.raise_for_status()
        self.call_count_today += 1
        return resp.json()

    def get_quote(self, symbol: str) -> dict:
        """Get live quote (price, open, high, low, volume) with 15-min cache."""
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
                "volume": row["volume"],
                "cached": True,
            }

        data = self._get("/quote", {"symbol": symbol})
        quote = {
            "symbol": symbol,
            "price": data.get("c"),
            "open": data.get("o"),
            "high": data.get("h"),
            "low": data.get("l"),
            "volume": data.get("v"),
            "timestamp": datetime.now(),
        }

        self._save_cache(cache, quote)
        quote["cached"] = False
        return quote

    def get_fundamentals(self, symbol: str) -> dict:
        """Get P/E, EPS, ROE, dividend yield."""
        data = self._get("/stock/metric", {"symbol": symbol})
        metrics = data.get("metric", {})
        return {
            "pe": metrics.get("peNormalizedAnnual"),
            "eps": metrics.get("epsNormalizedAnnual"),
            "roe": metrics.get("roe"),
            "dividend_yield": metrics.get("dividendYieldIndicatedAnnual"),
        }

    def get_news(self, symbol: str, limit: int = 3) -> list:
        """Get latest news for a symbol."""
        data = self._get(
            "/company-news",
            {"symbol": symbol, "from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"), "to": datetime.now().strftime("%Y-%m-%d")},
        )
        return [{"headline": item["headline"], "source": item["source"]} for item in data[:limit]]

    def get_insider_sentiment(self, symbol: str) -> dict:
        """Get MSPR (insider sentiment indicator)."""
        data = self._get("/stock/insider-sentiment", {"symbol": symbol})
        total = data.get("data", [{}])[0]
        return {
            "change": total.get("change"),
            "mspr": total.get("mspr"),
        }

    def get_analyst_recommendation(self, symbol: str) -> dict:
        """Get consensus analyst recommendation."""
        data = self._get("/stock/recommendation", {"symbol": symbol})
        if data:
            latest = data[0]
            return {
                "rating": latest.get("consensusEpsEstimate"),
                "target_price": latest.get("targetPrice"),
            }
        return {"rating": None, "target_price": None}

    def _load_cache(self) -> pl.DataFrame:
        """Load price cache or return empty DataFrame."""
        try:
            return read_parquet(CACHE_CONTAINER, CACHE_FILE)
        except Exception:
            return pl.DataFrame(
                {
                    "symbol": pl.Utf8,
                    "price": pl.Float64,
                    "open": pl.Float64,
                    "high": pl.Float64,
                    "low": pl.Float64,
                    "volume": pl.Int64,
                    "timestamp": pl.Datetime,
                }
            )

    def _save_cache(self, cache: pl.DataFrame, quote: dict) -> None:
        """Append quote to cache and save."""
        new_row = pl.DataFrame([quote])
        combined = pl.concat([cache, new_row], how="diagonal_relaxed")
        write_parquet(CACHE_CONTAINER, CACHE_FILE, combined)
