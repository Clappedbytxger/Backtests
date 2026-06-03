"""Tests for the backtest engine, especially look-ahead protection."""

import numpy as np
import pandas as pd

from quantlab.backtest import run_backtest
from quantlab.costs import CostModel


def _make_prices(returns: pd.Series) -> pd.DataFrame:
    close = 100 * (1 + returns).cumprod()
    return pd.DataFrame({"Close": close})


def test_no_lookahead_shift():
    """A signal that knows today's return must NOT capture it.

    Build a perfect-foresight signal = sign of *today's* return. Without a shift
    that would be a money machine; with the engine's shift the position is held
    the NEXT day, so the perfect-foresight edge disappears (no leakage).
    """
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    rng = np.random.default_rng(1)
    rets = pd.Series(rng.normal(0, 0.01, 200), index=idx)
    prices = _make_prices(rets)

    # Cheating signal: today's sign. Engine shifts it -> applied tomorrow.
    cheating = np.sign(prices["Close"].pct_change()).fillna(0.0)
    res = run_backtest(prices, cheating, cost_model=CostModel(
        commission_per_share=0, min_commission=0, slippage_bps=0, regulatory_bps=0))

    # If leakage existed, strategy return would equal |asset return| (huge Sharpe).
    # After the shift, correlation between position and same-day return is ~0.
    pos = res["position"]
    same_day = prices["Close"].pct_change().fillna(0.0)
    corr = np.corrcoef(pos.values[1:], same_day.values[1:])[0, 1]
    assert abs(corr) < 0.2  # no strong same-day alignment -> no leakage


def test_costs_reduce_returns():
    idx = pd.date_range("2020-01-01", periods=50, freq="B")
    rets = pd.Series([0.001] * 50, index=idx)
    prices = _make_prices(rets)
    # Alternate in/out every day -> lots of turnover.
    signal = pd.Series(([1.0, 0.0] * 25), index=idx)

    no_cost = run_backtest(prices, signal, cost_model=CostModel(
        commission_per_share=0, min_commission=0, slippage_bps=0, regulatory_bps=0))
    with_cost = run_backtest(prices, signal, cost_model=CostModel(slippage_bps=10))

    assert with_cost["returns"].sum() < no_cost["returns"].sum()


def test_trade_log_structure():
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    rets = pd.Series([0.01] * 20, index=idx)
    prices = _make_prices(rets)
    # Long for first 10 (held) days, then flat.
    signal = pd.Series([1.0] * 10 + [0.0] * 10, index=idx)
    res = run_backtest(prices, signal)
    trades = res["trades"]
    assert not trades.empty
    assert {"entry_date", "exit_date", "direction", "holding_days", "pnl"}.issubset(
        trades.columns
    )
    assert (trades["direction"] == 1).all()
