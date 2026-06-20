"""Tests for the event-driven backtester: parity with the vectorized engine + stops."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.backtest import run_backtest
from quantlab.backtest_event import run_event_backtest


def _prices(seed=0, n=600) -> pd.DataFrame:
    idx = pd.bdate_range("2015-01-01", periods=n)
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    op = close * (1 + rng.normal(0, 0.002, n))
    hi = close * (1 + np.abs(rng.normal(0, 0.004, n)))
    lo = close * (1 - np.abs(rng.normal(0, 0.004, n)))
    return pd.DataFrame(
        {
            "Open": op,
            "High": np.maximum.reduce([op, hi, close]),
            "Low": np.minimum.reduce([op, lo, close]),
            "Close": close,
            "Volume": 1e6,
        },
        index=idx,
    )


def test_parity_with_vectorized_no_stops():
    p = _prices()
    sig = pd.Series(np.random.default_rng(1).choice([0.0, 1.0, -1.0], len(p)), index=p.index)
    a = run_backtest(p, sig)
    b = run_event_backtest(p, sig)
    assert np.allclose(a["returns"].to_numpy(), b["returns"].to_numpy(), atol=1e-12)
    assert np.allclose(a["equity"].to_numpy(), b["equity"].to_numpy(), atol=1e-9)
    assert np.allclose(a["position"].to_numpy(), b["position"].to_numpy())


def test_bar_loop_parity_when_stop_never_triggers():
    """A stop so wide it never fires must reproduce the fast path exactly (loop parity)."""
    p = _prices(seed=5)
    sig = pd.Series(np.random.default_rng(2).choice([0.0, 1.0, -1.0], len(p)), index=p.index)
    fast = run_event_backtest(p, sig)
    looped = run_event_backtest(p, sig, stop_loss=0.99, take_profit=0.99)
    assert np.allclose(fast["returns"].to_numpy(), looped["returns"].to_numpy(), atol=1e-12)


def _flat_ohlc(n=10):
    idx = pd.bdate_range("2020-01-01", periods=n)
    close = np.full(n, 100.0)
    return idx, close.copy(), close.copy(), close.copy(), close.copy()  # idx, o, h, l, c


def test_stop_loss_caps_and_flattens():
    idx, o, h, l, c = _flat_ohlc()
    l[5] = 90.0  # 10% intrabar drop on bar 5
    p = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)
    r = run_event_backtest(p, pd.Series(1.0, index=idx), stop_loss=0.05)
    pos = r["position"].to_numpy()
    assert r["gross_returns"].to_numpy()[5] == pytest.approx(-0.05, abs=1e-9)  # capped at -5%
    assert pos[5] == 1.0 and pos[6] == 0.0 and pos[7] == 0.0  # held bar 5, suppressed after


def test_take_profit_caps_gain():
    idx, o, h, l, c = _flat_ohlc()
    h[4] = 110.0
    p = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)
    r = run_event_backtest(p, pd.Series(1.0, index=idx), take_profit=0.05)
    assert r["gross_returns"].to_numpy()[4] == pytest.approx(0.05, abs=1e-9)
    assert r["position"].to_numpy()[5] == 0.0


def test_short_stop_loss_mirror():
    idx, o, h, l, c = _flat_ohlc()
    h[5] = 110.0  # price spikes up -> short is stopped out
    p = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)
    r = run_event_backtest(p, pd.Series(-1.0, index=idx), stop_loss=0.05)
    assert r["gross_returns"].to_numpy()[5] == pytest.approx(-0.05, abs=1e-9)


def test_no_lookahead_clairvoyant_guardrail():
    p = _prices(seed=3)
    fwd = np.sign(p["Close"].pct_change().shift(-1)).fillna(0.0)
    r = run_event_backtest(p, fwd)
    assert r["gross_returns"].sum() > 1.0  # genuine foresight pays through the engine
