"""Shared test fixtures.

The backend persists everything as Parquet blobs in Azure Blob Storage via
`storage/blobs.py`. Unit tests must never touch Azure, so `FakeBlobStore` is an
in-memory stand-in keyed by (container, blob) → Polars DataFrame. Tests patch the
`read_parquet` / `write_parquet` names that each module imported, pointing them at
the fake. See tests/README.md for the rationale.
"""

from datetime import date

import polars as pl
import pytest

CONTAINER = "papertrading"


class FakeBlobStore:
    """In-memory replacement for storage.blobs. Mirrors its read/write/append
    semantics (read of a missing blob raises, like the real download)."""

    def __init__(self):
        self.data: dict[tuple[str, str], pl.DataFrame] = {}

    def read_parquet(self, container, blob):
        key = (container, blob)
        if key not in self.data:
            raise FileNotFoundError(f"{container}/{blob} not found")
        return self.data[key].clone()

    def write_parquet(self, container, blob, df):
        self.data[(container, blob)] = df.clone()

    def append_parquet(self, container, blob, df):
        try:
            existing = self.read_parquet(container, blob)
            combined = pl.concat([existing, df], how="diagonal_relaxed")
        except Exception:
            combined = df
        self.write_parquet(container, blob, combined)

    def seed(self, container, blob, df):
        self.data[(container, blob)] = df.clone()

    def patch(self, monkeypatch, module):
        """Redirect a module's imported read/write/append helpers to this store."""
        monkeypatch.setattr(module, "read_parquet", self.read_parquet, raising=False)
        monkeypatch.setattr(module, "write_parquet", self.write_parquet, raising=False)
        if hasattr(module, "append_parquet"):
            monkeypatch.setattr(module, "append_parquet", self.append_parquet, raising=False)

    def seed_papertrading(self, cash=100_000.0):
        """Seed empty, correctly-typed portfolio/trades blobs + a cash ledger with
        one row (matching what GET /api/setup creates)."""
        self.seed(CONTAINER, "portfolio.parquet", pl.DataFrame(
            schema={"symbol": pl.Utf8, "shares": pl.Int64,
                    "avg_cost": pl.Float64, "market_value": pl.Float64}))
        self.seed(CONTAINER, "trades.parquet", pl.DataFrame(
            schema={"date": pl.Date, "symbol": pl.Utf8, "shares": pl.Int64,
                    "price": pl.Float64, "side": pl.Utf8}))
        self.seed(CONTAINER, "cash_ledger.parquet",
                  pl.DataFrame({"date": [date.today()], "amount": [float(cash)]}))
        return self


@pytest.fixture
def blob_store():
    return FakeBlobStore()
