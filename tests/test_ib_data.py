"""Tests for the intraday data layer (pure helpers; no network / no gateway)."""

from __future__ import annotations

import pandas as pd

from quantlab.ib_data import _cache_path, _ib_contract, _normalize


def test_ib_contract_mapping():
    from ib_async import Crypto, Forex, Stock

    c, what = _ib_contract("BTC-USD")
    assert isinstance(c, Crypto) and what == "MIDPOINT"
    c, what = _ib_contract("EURUSD=X")
    assert isinstance(c, Forex) and what == "MIDPOINT"
    c, what = _ib_contract("AAPL")
    assert isinstance(c, Stock) and what == "TRADES"
    c, _ = _ib_contract("^GSPC")  # index proxy -> SPY stock
    assert isinstance(c, Stock) and c.symbol == "SPY"


def test_normalize_makes_tz_aware_ohlcv():
    raw = pd.DataFrame(
        {"open": [1, 2], "high": [1, 2], "low": [1, 2], "close": [1.5, 2.5], "volume": [10, 20]},
        index=pd.to_datetime(["2024-01-01 18:00", "2024-01-01 19:00"]),
    )
    df = _normalize(raw)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index.tz is not None
    assert df.index.hour.tolist() == [18, 19]  # time-of-day preserved


def test_cache_path_is_filesystem_safe():
    assert _cache_path("BTC-USD", "1h", "yf").name == "BTC-USD_1h_yf.parquet"
    assert "=" not in _cache_path("EURUSD=X", "1h", "ib").name
