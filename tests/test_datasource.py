"""Tests for the unified data layer (:mod:`quantlab.datasource`).

The yfinance path is exercised via a monkeypatched loader (no network); the Alpaca path
is checked for correct credential-gating + bar normalisation against a fake HTTP client.
"""

import pandas as pd
import pytest

from quantlab import datasource as ds


def test_get_bars_yfinance_delegates(monkeypatch):
    captured = {}

    def fake_get_prices(symbol, start=None, end=None, interval="1d"):
        captured.update(symbol=symbol, interval=interval)
        idx = pd.date_range("2024-01-01", periods=3, name="Date")
        return pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5,
                             "Volume": 100}, index=idx)

    monkeypatch.setattr("quantlab.data.get_prices", fake_get_prices)
    df = ds.get_bars("SPY", timeframe="1Day", provider="yfinance")
    assert captured == {"symbol": "SPY", "interval": "1d"}   # timeframe mapped
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_unknown_timeframe_and_provider():
    with pytest.raises(ValueError):
        ds.get_bars("SPY", timeframe="3Day")
    with pytest.raises(ValueError):
        ds.get_bars("SPY", provider="bloomberg")


def test_alpaca_requires_keys(monkeypatch):
    monkeypatch.setattr(ds, "_alpaca_creds", lambda: None)
    with pytest.raises(RuntimeError, match="Alpaca keys not set"):
        ds.get_bars("AAPL", provider="alpaca")


def test_alpaca_bars_normalised(monkeypatch):
    monkeypatch.setattr(ds, "_alpaca_creds", lambda: ("k", "s"))

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"bars": [
                {"t": "2024-01-02T05:00:00Z", "o": 10, "h": 11, "l": 9, "c": 10.5, "v": 1000},
                {"t": "2024-01-03T05:00:00Z", "o": 10.5, "h": 12, "l": 10, "c": 11.5, "v": 1200},
            ], "next_page_token": None}

    monkeypatch.setattr(ds, "httpx", type("M", (), {"get": staticmethod(lambda *a, **k: _Resp())}))
    df = ds.get_bars("AAPL", provider="alpaca")
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df["Close"].iloc[-1] == 11.5
    assert df.index.name == "Date"


def test_provider_status_reflects_keys(monkeypatch):
    monkeypatch.setattr(ds, "_alpaca_creds", lambda: None)
    st = {p["provider"]: p for p in ds.provider_status()}
    assert st["yfinance"]["available"] is True
    assert st["alpaca"]["available"] is False
    monkeypatch.setattr(ds, "_alpaca_creds", lambda: ("k", "s"))
    st2 = {p["provider"]: p for p in ds.provider_status()}
    assert st2["alpaca"]["available"] is True
