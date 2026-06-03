"""Unit tests for metrics against hand-computed values."""

import numpy as np
import pandas as pd

from quantlab import metrics


def test_total_and_cagr():
    # Two periods of +10% then -10% -> 0.99 cumulative.
    r = pd.Series([0.10, -0.10])
    assert abs(metrics.total_return(r) - (-0.01)) < 1e-12
    # One year of constant daily return compounding to known value.
    daily = pd.Series([0.001] * 252)
    expected = (1.001 ** 252) - 1
    assert abs(metrics.cagr(daily) - expected) < 1e-9


def test_sharpe_zero_vol_is_nan():
    r = pd.Series([0.01] * 50)  # no volatility
    assert np.isnan(metrics.sharpe_ratio(r))


def test_sharpe_positive_for_positive_drift():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.0005, 0.01, 1000))
    assert metrics.sharpe_ratio(r, risk_free_annual=0.0) > 0


def test_max_drawdown_known_path():
    # Equity: 1 -> 1.2 -> 0.9 -> ... worst DD from 1.2 to 0.9 = -25%.
    r = pd.Series([0.2, -0.25, 0.1])
    assert abs(metrics.max_drawdown(r) - (-0.25)) < 1e-9


def test_trade_stats():
    trades = pd.DataFrame(
        {"pnl": [0.05, -0.02, 0.03, -0.01], "holding_days": [5, 3, 4, 2]}
    )
    s = metrics.trade_stats(trades)
    assert s["n_trades"] == 4
    assert abs(s["win_rate"] - 0.5) < 1e-12
    # profit factor = (0.05+0.03) / (0.02+0.01) = 0.08/0.03
    assert abs(s["profit_factor"] - (0.08 / 0.03)) < 1e-9
    assert abs(s["avg_holding_days"] - 3.5) < 1e-12
