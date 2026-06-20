"""Tests for the DuckDB data lake — especially the PIT look-ahead guard."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.store import DataLake


def _make_lake(root) -> str:
    """Write a synthetic daily Parquet dataset (Date index) and return its id."""
    idx = pd.date_range("2020-01-01", "2020-12-31", freq="D")  # 366 days (leap)
    df = pd.DataFrame({"Close": np.arange(len(idx), dtype=float)}, index=idx)
    df.index.name = "Date"
    sub = root / "futures"
    sub.mkdir(parents=True)
    df.to_parquet(sub / "TEST_1d_abc.parquet")
    return "futures/TEST_1d_abc.parquet"


def test_list_and_read(tmp_path):
    ds = _make_lake(tmp_path)
    with DataLake(cache_dir=tmp_path) as lake:
        assert lake.list_datasets() == [ds]
        assert lake.list_datasets("futures") == [ds]
        assert lake.list_datasets("nonexistent") == []
        df = lake.read(ds)
        assert len(df) == 366
        assert set(df.columns) >= {"Date", "Close"}


def test_time_column_autodetect(tmp_path):
    ds = _make_lake(tmp_path)
    with DataLake(cache_dir=tmp_path) as lake:
        assert lake.time_column(ds) == "Date"


def test_as_of_never_leaks_future(tmp_path):
    """The core look-ahead guard: as_of() must never return a future-stamped row."""
    ds = _make_lake(tmp_path)
    asof = pd.Timestamp("2020-06-15")
    with DataLake(cache_dir=tmp_path) as lake:
        out = lake.as_of(ds, asof)
        assert len(out) > 0
        dates = pd.to_datetime(out["Date"])
        assert dates.max() <= asof            # nothing newer than as-of
        assert (dates <= asof).all()
        # one more calendar day of as-of -> exactly one more row
        out2 = lake.as_of(ds, "2020-06-16")
        assert len(out2) == len(out) + 1


def test_as_of_tz_aware_column(tmp_path):
    """Naive as-of against a tz-aware (TIMESTAMPTZ) column must still not leak."""
    idx = pd.date_range("2020-01-01", "2020-12-31", freq="D", tz="UTC")
    df = pd.DataFrame({"Close": np.arange(len(idx), dtype=float)}, index=idx)
    df.index.name = "Date"
    (tmp_path / "futures").mkdir(parents=True)
    df.to_parquet(tmp_path / "futures" / "TZ_1d.parquet")
    ds = "futures/TZ_1d.parquet"
    with DataLake(cache_dir=tmp_path) as lake:
        assert "WITH TIME ZONE" in lake._types(ds)["Date"]
        out = lake.as_of(ds, "2020-06-15")  # naive as-of, tz-aware column
        dates = pd.to_datetime(out["Date"], utc=True)
        assert dates.max() <= pd.Timestamp("2020-06-15", tz="UTC")


def test_as_of_missing_dataset_raises(tmp_path):
    _make_lake(tmp_path)
    with DataLake(cache_dir=tmp_path) as lake:
        try:
            lake.as_of("futures/does_not_exist.parquet", "2020-06-15")
        except FileNotFoundError:
            return
        raise AssertionError("expected FileNotFoundError for a missing dataset")
