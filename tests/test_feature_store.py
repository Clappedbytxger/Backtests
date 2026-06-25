"""Tests for the ML Feature Store — focus on the no-look-ahead guarantee.

Uses a synthetic OHLCV series (no network) and monkeypatches ``get_prices`` so the
store / leakage validator run fully offline and deterministically.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab import feature_store as fs


def _synthetic_ohlcv(n: int = 800, seed: int = 7) -> pd.DataFrame:
    """A deterministic geometric-random-walk OHLCV frame on business days."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n, name="Date")
    rets = rng.normal(0.0003, 0.012, n)
    close = 100.0 * np.exp(np.cumsum(rets))
    spread = np.abs(rng.normal(0.0, 0.006, n)) + 0.002
    open_ = close * (1.0 + rng.normal(0.0, 0.004, n))
    high = np.maximum(open_, close) * (1.0 + spread)
    low = np.minimum(open_, close) * (1.0 - spread)
    vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


@pytest.fixture
def patched_prices(monkeypatch):
    df = _synthetic_ohlcv()
    monkeypatch.setattr(fs, "get_prices", lambda *a, **k: df.copy())
    return df


def test_compute_features_shape(patched_prices):
    frame, timings = fs.compute_features(patched_prices)
    assert list(frame.columns) == [f.name for f in fs.REGISTRY]
    assert frame.index.equals(patched_prices.index)
    assert all(ms >= 0 for ms in timings.values())
    # RSI must stay in [0, 100]
    rsi = frame["rsi_14"].dropna()
    assert rsi.between(0, 100).all()


def test_no_lookahead_shift_invariance(patched_prices):
    """The core leakage proof: truncating the input must not change past values."""
    report = fs.validate_no_lookahead("SYNTH", n_checks=6)
    assert report["ok"], {k: v for k, v in report["factors"].items() if not v["ok"]}
    for name, r in report["factors"].items():
        assert r["max_abs_diff"] < 1e-9, f"{name} leaks: {r}"


def test_planted_leak_is_caught(patched_prices, monkeypatch):
    """A deliberately future-peeking factor must FAIL the validator (guard works)."""
    leaky = fs.FactorDef(
        "leaky", "momentum",
        lambda d: d["Close"].shift(-1) / d["Close"] - 1.0,  # tomorrow's return — leak!
        "intentional look-ahead",
    )
    monkeypatch.setattr(fs, "REGISTRY", [leaky])
    monkeypatch.setattr(fs, "FACTOR_BY_NAME", {"leaky": leaky})
    report = fs.validate_no_lookahead("SYNTH", n_checks=5)
    assert not report["ok"]
    assert not report["factors"]["leaky"]["ok"]


def test_store_roundtrip_and_time_travel(patched_prices, tmp_path):
    store = fs.FeatureStore(store_dir=tmp_path)
    summary = store.compute("SYNTH")
    assert summary["n_factors"] == len(fs.REGISTRY)
    assert store.is_built("SYNTH")

    # column projection: only the requested factor is loaded
    one = store.load("SYNTH", factors=["rsi_14"])
    assert list(one.columns) == ["rsi_14"]

    # time-travel: as_of slice equals a full load truncated at that date
    full = store.load("SYNTH")
    cut = full.index[500]
    travelled = store.load("SYNTH", as_of=cut)
    assert travelled.index.max() == cut
    pd.testing.assert_frame_equal(travelled, full.loc[full.index <= cut])

    # and the past values are identical (no revisioning / leakage through the store)
    pd.testing.assert_series_equal(travelled["macd_div"], full["macd_div"].loc[:cut])


def test_status_and_correlation(patched_prices, tmp_path):
    store = fs.FeatureStore(store_dir=tmp_path)
    store.compute("SYNTH")
    rows = store.status("SYNTH")
    assert len(rows) == len(fs.REGISTRY)
    assert all(r["status"] == "up-to-date" for r in rows)
    assert all(r["disk_bytes"] > 0 for r in rows)

    corr = store.correlation("SYNTH")
    assert len(corr["labels"]) == len(fs.REGISTRY)
    # diagonal is 1.0
    for i, lab in enumerate(corr["labels"]):
        assert corr["matrix"][i][i] == pytest.approx(1.0, abs=1e-6)
