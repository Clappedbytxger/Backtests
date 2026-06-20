"""Parity tests for the optional C++ speed kernel against NumPy / the Python engine.

Skips automatically when `quant_kernel` is not built, so the suite never depends
on a native build.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

quant_kernel = pytest.importorskip("quant_kernel")

from quantlab.backtest import run_backtest  # noqa: E402


def test_net_returns_matches_numpy():
    rng = np.random.default_rng(0)
    n = 5000
    position = rng.choice([-1.0, 0.0, 1.0], n).astype(float)
    ret = rng.normal(0.0, 0.01, n)
    cost = 3e-4

    turn = np.abs(np.diff(position, prepend=0.0))
    net_ref = position * ret - turn * cost
    net_k = quant_kernel.net_returns(position, ret, cost)
    assert np.allclose(net_k, net_ref, atol=1e-12)


def test_equity_curve_matches_numpy():
    rng = np.random.default_rng(1)
    net = rng.normal(0.0, 0.005, 5000)
    eq_ref = np.cumprod(1.0 + net)
    eq_k = quant_kernel.equity_curve(net)
    assert np.allclose(eq_k, eq_ref, atol=1e-10)


def test_kernel_reproduces_run_backtest_net_returns():
    """The kernel's net_returns must reproduce the vectorized engine's net stream."""
    idx = pd.bdate_range("2015-01-01", "2019-12-31")
    rng = np.random.default_rng(7)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(idx))))
    prices = pd.DataFrame({"Close": close}, index=idx)
    signal = pd.Series(rng.choice([0.0, 1.0], len(idx)), index=idx)

    bt = run_backtest(prices, signal)  # default IBKR cost model
    held = bt["position"].to_numpy()
    asset_ret = prices["Close"].pct_change().fillna(0.0).to_numpy()
    # recover the engine's per-side cost fraction from one turnover event
    turn = np.abs(np.diff(held, prepend=0.0))
    diff = (bt["gross_returns"].to_numpy() - bt["returns"].to_numpy())
    cost_frac = float(np.median(diff[turn > 0] / turn[turn > 0]))

    net_k = quant_kernel.net_returns(held, asset_ret, cost_frac)
    assert np.allclose(net_k, bt["returns"].to_numpy(), atol=1e-12)


def test_length_mismatch_raises():
    with pytest.raises(Exception):
        quant_kernel.net_returns(np.zeros(3), np.zeros(4), 0.0)
