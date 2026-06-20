"""Tests for the IStrategy contract: correctness, runner parity, look-ahead, parity util."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.backtest import run_backtest
from quantlab.seasonal import turn_of_month_signal
from quantlab.strategy import (
    IStrategy,
    TurnOfMonthStrategy,
    backtest_strategy,
    validate_parity,
)


def _prices(start="2010-01-01", end="2019-12-31", seed=0) -> pd.DataFrame:
    """Synthetic OHLCV on a business-day index (deterministic, no network)."""
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(idx))))
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1e6},
        index=idx,
    )


def test_reference_signal_matches_seasonal_builder():
    p = _prices()
    sig = TurnOfMonthStrategy().generate_signals(p)
    expected = turn_of_month_signal(p.index, 1, 3)
    pd.testing.assert_series_equal(sig, expected)
    assert set(np.unique(sig.values)) <= {0.0, 1.0}
    assert 0 < sig.sum() < len(sig)  # active, but not always-on


def test_runner_matches_direct_engine():
    """backtest_strategy must reproduce run_backtest with the raw signal exactly."""
    p = _prices()
    direct = run_backtest(p, turn_of_month_signal(p.index, 1, 3))
    via_if = backtest_strategy(TurnOfMonthStrategy(), p)
    pd.testing.assert_series_equal(via_if["returns"], direct["returns"])


def test_no_lookahead_causality():
    """Appending future bars must not change earlier signal values (no leakage)."""
    p = _prices("2010-01-01", "2019-12-31")
    strat = TurnOfMonthStrategy()
    full = strat.target_weights(p)
    trunc = strat.target_weights(p.loc[:"2018-06-30"])
    win = p.loc["2010-01-01":"2017-12-31"].index  # entirely before truncation
    pd.testing.assert_series_equal(full.reindex(win), trunc.reindex(win))


def test_parity_pass_and_fail():
    p = _prices()
    r = backtest_strategy(TurnOfMonthStrategy(), p)["returns"]
    ok = validate_parity(r, r.copy())
    assert ok["passed"] and ok["corr"] > 0.999
    # shuffle dates -> relationship destroyed -> parity must fail
    bad = r.copy()
    bad[:] = np.random.default_rng(1).permutation(r.values)
    assert not validate_parity(r, bad)["passed"]


def test_clairvoyant_signal_is_rewarded_guardrail():
    """Sanity guardrail (cf. test_weinstein): a signal that legitimately foresees
    next-day returns must be very profitable through the engine — proving the
    harness would expose accidental look-ahead rather than mask it."""
    p = _prices(seed=3)
    fwd_sign = np.sign(p["Close"].pct_change().shift(-1)).fillna(0.0)

    class _Oracle(IStrategy):
        id = "oracle"
        name = "planted clairvoyant"

        def generate_signals(self, prices):
            return fwd_sign

    bt = backtest_strategy(_Oracle(), p)
    assert bt["gross_returns"].sum() > 1.0  # foresight pays a lot
