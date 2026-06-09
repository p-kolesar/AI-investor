"""Unit tests for market.finnhub.FinnhubClient.

Covers the cost-guardrail and caching logic plus the response-mapping for each
market-data endpoint. No real HTTP — `_get` is stubbed; storage is the in-memory
fake. (time.sleep is patched so the throttle never actually blocks.)
"""

from datetime import datetime, timedelta

import polars as pl
import pytest

from market import finnhub
from market.finnhub import FinnhubClient, DAILY_CALL_CAP, RATE_LIMIT_PER_MIN

CONTAINER = finnhub.CACHE_CONTAINER


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    return FinnhubClient()


def test_init_requires_api_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    with pytest.raises(ValueError, match="FINNHUB_API_KEY"):
        FinnhubClient()


# ---- Response parsers ------------------------------------------------------

def test_get_fundamentals_maps_metric_fields(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: {
        "metric": {"peNormalizedAnnual": 25.5, "epsNormalizedAnnual": 6.1,
                   "roeRfy": 31.2, "dividendYieldIndicatedAnnual": 0.5}})
    assert client.get_fundamentals("AAPL") == {
        "pe": 25.5, "eps": 6.1, "roe": 31.2, "dividend_yield": 0.5}


def test_get_analyst_recommendation_uses_latest(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: [
        {"period": "2026-06-01", "strongBuy": 10, "buy": 20, "hold": 3, "sell": 1, "strongSell": 0},
        {"period": "2026-05-01", "strongBuy": 8, "buy": 18, "hold": 5, "sell": 2, "strongSell": 1}])
    rec = client.get_analyst_recommendation("AAPL")
    assert rec["period"] == "2026-06-01"
    assert rec["strong_buy"] == 10 and rec["sell"] == 1


def test_get_analyst_recommendation_empty_returns_nones(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: [])
    rec = client.get_analyst_recommendation("AAPL")
    assert rec == {"period": None, "strong_buy": None, "buy": None,
                   "hold": None, "sell": None, "strong_sell": None}


def test_get_price_target_maps_fields(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: {
        "targetHigh": 300, "targetLow": 200, "targetMean": 250, "targetMedian": 255})
    assert client.get_price_target("AAPL") == {
        "target_high": 300, "target_low": 200, "target_mean": 250, "target_median": 255}


def test_get_earnings_returns_next_date(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: {"earningsCalendar": [{"date": "2026-07-01"}]})
    assert client.get_earnings("AAPL") == {"next_earnings_date": "2026-07-01"}


def test_get_earnings_none_when_empty(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: {"earningsCalendar": []})
    assert client.get_earnings("AAPL") == {"next_earnings_date": None}


def test_get_news_limits_results(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: [
        {"headline": f"h{i}", "source": f"s{i}"} for i in range(5)])
    news = client.get_news("AAPL")  # default limit 3
    assert len(news) == 3
    assert news[0] == {"headline": "h0", "source": "s0"}


def test_get_insider_sentiment_uses_first_row(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda ep, p: {"data": [{"change": 100, "mspr": 50.5}]})
    assert client.get_insider_sentiment("AAPL") == {"change": 100, "mspr": 50.5}


# ---- Quote cache (15-min TTL) ---------------------------------------------

def test_get_quote_returns_fresh_cache_without_calling_api(client, blob_store, monkeypatch):
    blob_store.patch(monkeypatch, finnhub)
    blob_store.seed(CONTAINER, finnhub.CACHE_FILE, pl.DataFrame({
        "symbol": ["AAPL"], "price": [150.0], "open": [148.0], "high": [151.0],
        "low": [147.0], "timestamp": [datetime.now()]}))

    def _boom(*a, **k):
        raise AssertionError("_get must not be called on a cache hit")
    monkeypatch.setattr(client, "_get", _boom)

    quote = client.get_quote("AAPL")
    assert quote["cached"] is True
    assert quote["price"] == 150.0


def test_get_quote_fetches_and_caches_on_miss(client, blob_store, monkeypatch):
    blob_store.patch(monkeypatch, finnhub)
    blob_store.seed(CONTAINER, finnhub.CACHE_FILE, pl.DataFrame({
        "symbol": ["AAPL"], "price": [150.0], "open": [148.0], "high": [151.0],
        "low": [147.0], "timestamp": [datetime.now() - timedelta(minutes=30)]}))  # stale
    monkeypatch.setattr(client, "_get", lambda ep, p: {"c": 99.0, "o": 98.0, "h": 100.0, "l": 97.0})

    quote = client.get_quote("AAPL")
    assert quote["cached"] is False
    assert quote["price"] == 99.0
    # the fresh quote was written back to the cache
    cached = blob_store.read_parquet(CONTAINER, finnhub.CACHE_FILE).filter(pl.col("symbol") == "AAPL")
    assert cached.row(0, named=True)["price"] == 99.0


# ---- Daily call cap (persisted) -------------------------------------------

def test_enforce_daily_cap_raises_at_limit(client, blob_store, monkeypatch):
    blob_store.patch(monkeypatch, finnhub)
    blob_store.seed(CONTAINER, finnhub.USAGE_FILE, pl.DataFrame({
        "date": [datetime.now().date()], "calls": [DAILY_CALL_CAP]}))
    with pytest.raises(RuntimeError, match="daily call cap"):
        client._enforce_daily_cap()


def test_enforce_daily_cap_increments_counter(client, blob_store, monkeypatch):
    blob_store.patch(monkeypatch, finnhub)  # no usage blob yet → starts from 0
    client._enforce_daily_cap()
    usage = blob_store.read_parquet(CONTAINER, finnhub.USAGE_FILE)
    today = usage.filter(pl.col("date") == datetime.now().date())
    assert today.row(0, named=True)["calls"] == 1


# ---- Per-minute throttle ---------------------------------------------------

def test_throttle_sleeps_when_over_limit(client, monkeypatch):
    slept = []
    monkeypatch.setattr(finnhub.time, "sleep", lambda s: slept.append(s))
    import time
    client._call_times = [time.time()] * RATE_LIMIT_PER_MIN  # at the cap
    client._throttle_per_minute()
    assert slept, "expected a throttle sleep when at the per-minute cap"


def test_throttle_does_not_sleep_when_idle(client, monkeypatch):
    slept = []
    monkeypatch.setattr(finnhub.time, "sleep", lambda s: slept.append(s))
    client._call_times = []
    client._throttle_per_minute()
    assert slept == []
