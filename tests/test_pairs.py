"""Sanity + causality tests for the cointegration / pairs engine (quantlab.pairs).

Synthetic ground truth: we *construct* a cointegrated pair (A = β·B + stationary
noise) and an independent pair (two random walks), then check the engine accepts
the former and rejects the latter, recovers β, and that the tradable z-score is
look-ahead-safe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab import pairs


def _cointegrated_pair(n=1200, beta=1.7, seed=1):
    """B is a random walk; A = 5 + beta*B + stationary OU noise ⇒ cointegrated."""
    rng = np.random.default_rng(seed)
    b = 50 + np.cumsum(rng.normal(0, 0.5, n))
    # stationary AR(1) residual (fast mean reversion)
    eps = np.zeros(n)
    for i in range(1, n):
        eps[i] = 0.85 * eps[i - 1] + rng.normal(0, 0.4)
    a = 5 + beta * b + eps  # linear cointegrating relation with slope beta
    idx = pd.bdate_range("2018-01-01", periods=n)
    return (pd.Series(a, index=idx, name="A"),
            pd.Series(b, index=idx, name="B"), beta)


def _independent_walks(n=1200, seed=2):
    rng = np.random.default_rng(seed)
    a = 100 + np.cumsum(rng.normal(0, 1.0, n))
    b = 100 + np.cumsum(rng.normal(0, 1.0, n))
    idx = pd.bdate_range("2018-01-01", periods=n)
    return pd.Series(a, index=idx, name="A"), pd.Series(b, index=idx, name="B")


def test_cointegrated_pair_is_detected():
    a, b, beta = _cointegrated_pair()
    st = pairs.engle_granger(a, b, use_log=False)
    assert st is not None
    assert st.cointegrated, f"should be cointegrated, ADF p={st.adf_pvalue}"
    assert st.adf_pvalue < 0.05
    # hedge ratio recovered within a sensible tolerance
    assert abs(st.hedge_ratio - beta) / beta < 0.15
    # a fast-reverting spread has a small, finite, positive half-life
    assert 0 < st.half_life < 200


def test_independent_walks_are_rejected():
    a, b = _independent_walks()
    st = pairs.engle_granger(a, b, use_log=False)
    assert st is not None
    assert not st.cointegrated, f"independent walks must not be cointegrated (p={st.adf_pvalue})"


def test_half_life_infinite_for_random_walk():
    rng = np.random.default_rng(3)
    rw = pd.Series(np.cumsum(rng.normal(0, 1, 800)))
    assert pairs.half_life(rw) > 100  # a random walk barely reverts → large/inf


def test_zscore_is_causal():
    """z[t] must use only spread bars <= t (truncation stability)."""
    a, b, _ = _cointegrated_pair()
    sp = pairs.spread_series(a, b, hedge_ratio=1.7, intercept=0.0, use_log=False)
    full = pairs.zscore(sp, window=60)
    rng = np.random.default_rng(0)
    for t in rng.choice(range(200, len(sp)), size=15, replace=False):
        trunc = pairs.zscore(sp.iloc[: t + 1], window=60)
        a_, b_ = full.iloc[t], trunc.iloc[-1]
        if np.isnan(a_) and np.isnan(b_):
            continue
        assert abs(float(a_) - float(b_)) < 1e-9, f"z not causal at {t}"


def test_signal_thresholds():
    assert pairs.signal_from_z(2.5) == "short_spread"
    assert pairs.signal_from_z(-2.5) == "long_spread"
    assert pairs.signal_from_z(0.3) == "neutral"
    assert pairs.signal_from_z(float("nan")) == "neutral"


def test_signal_series_holds_until_reversion():
    """Position is entered at |z|>=entry and held until z reverts through ~0."""
    z = pd.Series([0, 2.3, 1.5, 0.8, 0.2, -0.1, -2.4, -1.0, 0.0])
    pos = pairs.signal_series(z, entry=2.0, exit_band=0.5)
    assert pos.iloc[1] == -1          # short entered at z=2.3
    assert pos.iloc[3] == -1          # still held at z=0.8 (outside exit band)
    assert pos.iloc[4] == 0           # exited as z fell to 0.2
    assert pos.iloc[6] == +1          # long entered at z=-2.4


def test_backtest_finds_edge_on_mean_reverting_pair():
    """A genuinely mean-reverting spread should backtest as a positive-OOS edge."""
    a, b, _ = _cointegrated_pair(n=1500, seed=11)
    bt = pairs.backtest_pair(a, b, use_log=False, cost_bps=2.0, with_curve=True)
    assert bt is not None
    assert bt["n_trades"] >= pairs.EDGE_MIN_TRADES
    assert bt["sharpe_oos"] > 0  # the reversion persists out-of-sample
    assert bt["is_edge"] is True
    # curve is monotone-ish positive and split date present
    assert bt["split_date"] is not None
    assert len(bt["curve"]) > 10


def test_backtest_rejects_independent_walks_as_edge():
    """Two independent random walks must NOT be flagged as a tradable edge."""
    a, b = _independent_walks(n=1500, seed=12)
    bt = pairs.backtest_pair(a, b, use_log=False, cost_bps=5.0)
    assert bt is not None
    assert bt["is_edge"] is False


def test_backtest_beta_is_in_sample_only():
    """OOS must use IS-fitted beta (honest split) — beta_is is reported."""
    a, b, beta = _cointegrated_pair(n=1500, seed=13)
    bt = pairs.backtest_pair(a, b, use_log=False)
    assert bt is not None
    assert "beta_is" in bt and bt["beta_is"] is not None
    # IS-fitted beta still recovers the true slope reasonably
    assert abs(bt["beta_is"] - beta) / beta < 0.2


def test_scan_returns_sorted_by_abs_z():
    a, b, _ = _cointegrated_pair(seed=4)
    a2, b2 = _independent_walks(seed=5)
    px = pd.concat([a.rename("AA"), b.rename("BB"),
                    a2.rename("CC"), b2.rename("DD")], axis=1)
    res = pairs.scan_pairs(px, corr_threshold=0.5, use_log=False)
    # the constructed cointegrated pair must appear
    found = {(s.a, s.b) for s in res}
    assert ("AA", "BB") in found or ("BB", "AA") in found
    # sorted by |z| descending
    zs = [abs(s.z_score) for s in res if not np.isnan(s.z_score)]
    assert zs == sorted(zs, reverse=True)
