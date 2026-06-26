"""Pins the agent's hard look-ahead guard (quantlab.causality.assess_causality).

The Alpha Factory's #1 failure mode is a model writing a future-peeking signal
(``Close.shift(-1)`` → fake Sharpe 8+). These tests prove the guard catches the
look-ahead families and clears genuinely causal signals.
"""
import numpy as np
import pandas as pd

from quantlab.causality import assess_causality


def _prices(n=400, seed=0):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1.0}, index=idx)


def test_negative_shift_lookahead_is_caught():
    """The classic cheat: long if TOMORROW closes higher than today."""
    px = _prices()

    def make(p):
        c = p["Close"]
        return (c.shift(-1) > c).astype(float).reindex(p.index).fillna(0.0)

    r = assess_causality(make, px)
    assert r["causal"] is False
    assert r["violations"] > 0


def test_future_gap_lookahead_is_caught():
    """post-market gap = Close.shift(-1) - Open (the AF-0110 SPY bug)."""
    px = _prices()

    def make(p):
        gap = p["Close"].shift(-1) - p["Open"]
        return np.sign(gap).reindex(p.index).fillna(0.0)

    assert assess_causality(make, px)["causal"] is False


def test_full_sample_normalisation_is_caught():
    """z-score vs FULL-SAMPLE mean/std leaks the future into bar t."""
    px = _prices()

    def make(p):
        c = p["Close"]
        z = (c - c.mean()) / c.std()
        return z.clip(-1, 1).reindex(p.index).fillna(0.0)

    assert assess_causality(make, px)["causal"] is False


def test_trailing_signal_passes():
    """A trailing SMA cross is decision-time honest → must pass."""
    px = _prices()

    def make(p):
        c = p["Close"]
        return (c.rolling(10).mean() > c.rolling(30).mean()).astype(float).reindex(p.index).fillna(0.0)

    r = assess_causality(make, px)
    assert r["causal"] is True
    assert r["violations"] == 0


def test_shift_plus_one_passes():
    """Looking BACKWARD (shift(+1)) is fine."""
    px = _prices()

    def make(p):
        c = p["Close"]
        return (c.shift(1) < c).astype(float).reindex(p.index).fillna(0.0)

    assert assess_causality(make, px)["causal"] is True
