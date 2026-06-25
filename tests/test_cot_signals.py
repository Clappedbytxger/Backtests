"""Math + signal tests for the COT positioning engine (quantlab.cot), no network."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab import cot


def test_cot_index_bounds_and_extremes():
    # a clean ramp: last value is the max → index 100, first values → low
    net = pd.Series(np.arange(200, dtype=float))
    idx = cot.cot_index(net, window=156)
    assert idx.iloc[-1] == 100.0
    assert (idx >= 0).all() and (idx <= 100).all()
    # a flat window is neutral (50), never NaN/inf
    flat = pd.Series([5.0] * 200)
    fidx = cot.cot_index(flat, window=156)
    assert (fidx == 50.0).all()


def test_rolling_zscore_flags_outlier():
    rng = np.random.default_rng(0)
    net = pd.Series(rng.normal(0, 1, 300))
    net.iloc[-1] = 8.0  # a large spike
    z = cot.rolling_zscore(net, window=156)
    assert z.iloc[-1] > 2.0


def test_classify_signal_logic():
    bull = cot.classify_signal(95.0, 2.5)
    assert bull["bias"] == "bullish" and bull["severity"] == "extreme"
    bear = cot.classify_signal(8.0, -2.4)
    assert bear["bias"] == "bearish" and "Overcrowded" in bear["status"]
    neutral = cot.classify_signal(50.0, 0.1)
    assert neutral["bias"] == "neutral"
    # None inputs degrade to neutral, never crash
    assert cot.classify_signal(None, None)["bias"] == "neutral"


def test_compute_cot_columns_on_synthetic(monkeypatch):
    """compute_cot derives net/index/z from a stubbed loader (no network)."""
    ref = pd.date_range("2021-01-05", periods=200, freq="W-TUE", name="ref_date")
    rng = np.random.default_rng(1)
    raw = pd.DataFrame({
        "open_interest": 1e6 + rng.normal(0, 1e4, 200),
        "comm_long": 200000 + rng.normal(0, 5000, 200),
        "comm_short": 250000 + rng.normal(0, 5000, 200),
        "noncomm_long": 180000 + rng.normal(0, 5000, 200),
        "noncomm_short": 120000 + rng.normal(0, 5000, 200),
    }, index=ref)
    raw["hedging_pressure"] = (raw["comm_short"] - raw["comm_long"]) / raw["open_interest"]
    raw["release_date"] = raw.index + pd.Timedelta(days=3)
    monkeypatch.setattr(cot.cot_data, "get_cot", lambda root, **k: raw)

    df = cot.compute_cot("GC", window=156)
    for col in ("comm_net", "noncomm_net", "comm_index", "comm_z", "noncomm_index", "noncomm_z"):
        assert col in df.columns
    assert (df["comm_net"] == raw["comm_long"] - raw["comm_short"]).all()
    assert df["comm_index"].between(0, 100).all()


def test_factor_panel_is_pit_shifted(monkeypatch):
    """factor_panel must not leak the Friday release into the same-day decision."""
    ref = pd.DatetimeIndex(["2024-01-02", "2024-01-09"], name="ref_date")
    raw = pd.DataFrame({
        "open_interest": [1e6, 1e6],
        "comm_long": [20.0, 30.0], "comm_short": [60.0, 40.0],
        "noncomm_long": [50.0, 40.0], "noncomm_short": [10.0, 30.0],
    }, index=ref)
    raw["hedging_pressure"] = (raw["comm_short"] - raw["comm_long"]) / raw["open_interest"]
    raw["release_date"] = raw.index + pd.Timedelta(days=3)
    monkeypatch.setattr(cot.cot_data, "get_cot", lambda root, **k: raw)

    days = pd.bdate_range("2024-01-02", "2024-01-16")
    panel = cot.factor_panel("GC", days, factor="comm_net", window=10)
    # Friday 2024-01-05 release must not be visible same day; Monday it is.
    assert pd.isna(panel.loc[pd.Timestamp("2024-01-05")])
    assert panel.loc[pd.Timestamp("2024-01-08")] == (20.0 - 60.0)
