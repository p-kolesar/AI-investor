"""Unit tests for storage.blobs.append_parquet.

append_parquet is read-modify-write: it unions onto the existing blob, or writes
the new frame alone if the blob doesn't exist yet. Azure I/O (read/write) is
patched out; we assert the concat behaviour.
"""

import polars as pl

from storage import blobs


def test_append_unions_onto_existing(monkeypatch):
    existing = pl.DataFrame({"a": [1]})
    written = {}
    monkeypatch.setattr(blobs, "read_parquet", lambda c, b: existing.clone())
    monkeypatch.setattr(blobs, "write_parquet", lambda c, b, df: written.update({(c, b): df}))

    blobs.append_parquet("cont", "x.parquet", pl.DataFrame({"a": [2]}))

    assert written[("cont", "x.parquet")]["a"].to_list() == [1, 2]


def test_append_writes_new_when_blob_missing(monkeypatch):
    written = {}

    def _missing(c, b):
        raise FileNotFoundError("no such blob")

    monkeypatch.setattr(blobs, "read_parquet", _missing)
    monkeypatch.setattr(blobs, "write_parquet", lambda c, b, df: written.update({(c, b): df}))

    blobs.append_parquet("cont", "y.parquet", pl.DataFrame({"a": [9]}))

    assert written[("cont", "y.parquet")]["a"].to_list() == [9]
