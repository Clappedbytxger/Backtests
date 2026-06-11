"""Tests for the cross-sectional engine — look-ahead safety is the headline.

The planted-signal test is the critical one: a signal that perfectly knows each
instrument's *next-day* return must NOT produce a positive backtest, because the
engine shifts weights by one bar. If it ever leaks, this test goes green-to-rich
and catches it.
"""

import numpy as np
import pandas as pd

from quantlab.cross_sectional import (
    momentum_signal,
    run_cross_sectional,
    _rebalance_dates,
)


def _panel(n_days=600, n_assets=8, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=n_days)
    rets = rng.normal(0.0003, 0.01, size=(n_days, n_assets))
    prices = 100 * np.exp(np.cumsum(rets, axis=0))
    cols = [f"A{i}" for i in range(n_assets)]
    return pd.DataFrame(prices, index=dates, columns=cols)


def test_future_signal_does_not_leak():
    """A clairvoyant signal (tomorrow's return) must not earn — weights are
    shifted, so it can only act one bar late."""
    prices = _panel()
    next_day_ret = prices.pct_change().shift(-1)  # knows the future
    res = run_cross_sectional(prices, next_day_ret, rebalance="ME", cost_bps_per_side=0.0)
    # If look-ahead were present this would be hugely positive; it must be ~noise.
    assert res["returns"].mean() < 0.002


def test_past_signal_on_planted_trend_earns():
    """Build a panel where one asset has a persistent uptrend the others lack;
    momentum should overweight it long and produce a positive gross spread."""
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2018-01-01", periods=600)
    base = rng.normal(0.0, 0.01, size=(600, 6))
    base[:, 0] += 0.003   # persistent winner
    base[:, 1] -= 0.003   # persistent loser
    prices = pd.DataFrame(100 * np.exp(np.cumsum(base, axis=0)), index=dates,
                          columns=[f"A{i}" for i in range(6)])
    sig = momentum_signal(prices, lookback=252, skip=21)
    res = run_cross_sectional(prices, sig, rebalance="ME", quantile=0.34,
                              cost_bps_per_side=0.0)
    assert res["gross_returns"].sum() > 0


def test_long_short_is_dollar_neutral():
    prices = _panel()
    sig = momentum_signal(prices, lookback=200, skip=10)
    res = run_cross_sectional(prices, sig, long_short=True, leg_weight=1.0)
    held = res["weights"]
    active = held[held.abs().sum(axis=1) > 0]
    # Net exposure ~0, gross ~2 on active days.
    assert active.sum(axis=1).abs().max() < 1e-9
    assert np.allclose(active.abs().sum(axis=1), 2.0, atol=1e-9)


def test_costs_reduce_returns():
    prices = _panel()
    sig = momentum_signal(prices, lookback=200, skip=10)
    free = run_cross_sectional(prices, sig, cost_bps_per_side=0.0)["returns"].sum()
    costed = run_cross_sectional(prices, sig, cost_bps_per_side=10.0)["returns"].sum()
    assert costed < free


def test_rebalance_dates_are_month_ends():
    prices = _panel()
    rb = _rebalance_dates(prices.index, "ME")
    # one per calendar month, each an actual index member
    assert all(d in prices.index for d in rb)
    assert len(rb) == len(pd.Series(prices.index).dt.to_period("M").unique())
