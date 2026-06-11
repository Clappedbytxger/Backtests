"""ML-portfolio engine guards: neutrality, look-ahead, clairvoyant sanity."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantlab.ml_portfolio import (  # noqa: E402
    quintile_ls_weights,
    run_buffered_long_portfolio,
    run_ml_portfolio,
)

RNG = np.random.default_rng(42)
DATES = pd.bdate_range("2015-01-01", "2020-12-31")
COLS = list("ABCDEFGHIJKLMNOPQ")  # 17 names like the real universe


def _random_returns() -> pd.DataFrame:
    return pd.DataFrame(
        RNG.normal(0, 0.01, size=(len(DATES), len(COLS))), index=DATES, columns=COLS
    )


def test_weights_dollar_neutral_and_gross_two():
    row = pd.Series(RNG.normal(size=len(COLS)), index=COLS)
    vol = pd.Series(RNG.uniform(0.05, 0.4, size=len(COLS)), index=COLS)
    w = quintile_ls_weights(row, vol, quantile=0.2, min_names=8)
    assert abs(w.sum()) < 1e-12
    assert abs(w.abs().sum() - 2.0) < 1e-12
    # Inverse-vol: within the long leg, lower vol => larger weight.
    longs = w[w > 0]
    vols = vol[longs.index]
    assert (longs.sort_values().index == vols.sort_values(ascending=False).index).all()


def test_min_names_guard():
    row = pd.Series([1.0, 2.0, np.nan, np.nan], index=list("ABCD"))
    w = quintile_ls_weights(row, None, min_names=4)
    assert (w == 0).all()


def test_clairvoyant_wins_and_lookahead_blocked():
    """Predictions = NEXT day's return must print money through the engine's
    shift; predictions = SAME day's return must not (the engine shifts them
    out of their own day)."""
    rets = _random_returns()
    clairvoyant = rets.shift(-1)  # at close t knows t+1's return (illegal info)
    res = run_ml_portfolio(rets, clairvoyant, rebalance="W", cost_bps_per_side=0.0)
    sharpe_clair = res["returns"].mean() / res["returns"].std() * np.sqrt(252)

    same_day = rets.copy()  # signal == today's already-realized return
    res2 = run_ml_portfolio(rets, same_day, rebalance="W", cost_bps_per_side=0.0)
    sharpe_same = res2["returns"].mean() / res2["returns"].std() * np.sqrt(252)

    assert sharpe_clair > 3.0, "engine failed to monetize planted future info"
    assert abs(sharpe_same) < 1.5, "same-day info leaked through the shift"


def test_long_only_weights():
    row = pd.Series(RNG.normal(size=len(COLS)), index=COLS)
    w = quintile_ls_weights(row, None, quantile=0.2, min_names=8, long_only=True)
    assert (w >= 0).all()
    assert abs(w.sum() - 1.0) < 1e-12


def test_buffer_reduces_turnover_keeps_held_in_band():
    """The buffered book must (a) trade less than the plain quantile book on
    noisy predictions and (b) only ever hold names inside the buffer band."""
    rets = _random_returns()
    preds = pd.DataFrame(
        RNG.normal(size=rets.shape), index=rets.index, columns=rets.columns
    )
    plain = run_ml_portfolio(
        rets, preds, rebalance="W", quantile=0.25, cost_bps_per_side=0.0,
        long_only=True,
    )
    buffered = run_buffered_long_portfolio(
        rets, preds, rebalance="W", quantile=0.25, buffer_mult=2.0,
        cost_bps_per_side=0.0,
    )
    assert buffered["turnover"].sum() < plain["turnover"].sum() * 0.85

    # band invariant: every held name ranks inside buffer_mult*quantile
    held = buffered["weights"]
    rb = buffered["rebalance_dates"]
    for dt in rb[5:25]:
        nxt = held.index[held.index.get_loc(dt) + 1]
        names = held.columns[held.loc[nxt] > 0]
        if len(names) == 0:
            continue
        s = preds.loc[dt].dropna()
        band = int(round(2.0 * 0.25 * len(s)))
        top_band = set(s.sort_values(ascending=False).index[:band])
        assert set(names) <= top_band


def test_buffered_no_lookahead():
    """Planted clairvoyant must win, same-day signal must not (mirrors the
    plain engine's guard)."""
    rets = _random_returns()
    res = run_buffered_long_portfolio(
        rets, rets.shift(-1), rebalance="W", cost_bps_per_side=0.0
    )
    sharpe_clair = res["returns"].mean() / res["returns"].std() * np.sqrt(252)
    res2 = run_buffered_long_portfolio(
        rets, rets.copy(), rebalance="W", cost_bps_per_side=0.0
    )
    sharpe_same = res2["returns"].mean() / res2["returns"].std() * np.sqrt(252)
    assert sharpe_clair > 2.0
    assert abs(sharpe_same) < 1.5


def test_costs_reduce_returns():
    rets = _random_returns()
    preds = pd.DataFrame(
        RNG.normal(size=rets.shape), index=rets.index, columns=rets.columns
    )
    free = run_ml_portfolio(rets, preds, cost_bps_per_side=0.0)
    paid = run_ml_portfolio(rets, preds, cost_bps_per_side=10.0)
    assert paid["returns"].sum() < free["returns"].sum()
    assert (free["gross_returns"] - paid["gross_returns"]).abs().max() < 1e-15
