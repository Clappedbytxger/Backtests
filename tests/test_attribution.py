"""Tests for the Performance Attribution Engine.

The critical validation: the Brinson-Fachler effects must sum **exactly** to the
active return (R_p − R_b). Plus OLS recovers a planted alpha/beta and the rolling
factor tracks a regime shift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab import attribution as at


# ── Brinson-Fachler ─────────────────────────────────────────────────────────────


def test_brinson_identity_exact():
    """Σ(allocation + selection + interaction) == R_p − R_b to machine precision."""
    wp = {"Equity": 0.6, "Bonds": 0.1, "Crypto": 0.3}
    rp = {"Equity": 0.08, "Bonds": 0.01, "Crypto": 0.25}
    wb = {"Equity": 0.5, "Bonds": 0.4, "Crypto": 0.1}
    rb = {"Equity": 0.06, "Bonds": 0.02, "Crypto": 0.15}
    res = at.brinson_fachler(wp, rp, wb, rb)
    assert abs(res.residual) < 1e-12
    assert res.allocation_total + res.selection_total + res.interaction_total == pytest.approx(
        res.active_return, abs=1e-12)
    assert res.active_return == pytest.approx(res.portfolio_return - res.benchmark_return, abs=1e-12)


def test_brinson_waterfall_arrives_at_portfolio():
    wp = {"A": 0.7, "B": 0.3}
    rp = {"A": 0.10, "B": -0.02}
    wb = {"A": 0.5, "B": 0.5}
    rb = {"A": 0.07, "B": 0.03}
    res = at.brinson_fachler(wp, rp, wb, rb)
    steps = res.waterfall()
    assert steps[0]["label"] == "Benchmark"
    assert steps[-1]["label"] == "Portfolio"
    # cumulative of the last step equals the portfolio return
    assert steps[-1]["cumulative"] == pytest.approx(res.portfolio_return, abs=1e-12)
    # the running cumulative after interaction equals portfolio return
    assert steps[-2]["cumulative"] == pytest.approx(res.portfolio_return, abs=1e-12)


def test_brinson_pure_selection():
    """Same weights in both books → allocation 0, all active return is selection+interaction."""
    wp = wb = {"A": 0.5, "B": 0.5}
    rp = {"A": 0.10, "B": 0.05}
    rb = {"A": 0.06, "B": 0.04}
    res = at.brinson_fachler(wp, rp, wb, rb)
    assert res.allocation_total == pytest.approx(0.0, abs=1e-12)
    assert res.interaction_total == pytest.approx(0.0, abs=1e-12)  # (wp-wb)=0
    assert res.selection_total == pytest.approx(res.active_return, abs=1e-12)


def test_brinson_unnormalised_weights():
    """Weights given as counts get normalised; identity still holds."""
    res = at.brinson_fachler({"A": 3, "B": 1}, {"A": 0.1, "B": 0.0},
                             {"A": 1, "B": 1}, {"A": 0.05, "B": 0.05})
    assert abs(res.residual) < 1e-12


# ── factor regression ───────────────────────────────────────────────────────────


def test_ols_recovers_planted_alpha_beta():
    rng = np.random.default_rng(0)
    n = 1000
    idx = pd.bdate_range("2018-01-01", periods=n)
    bench = pd.Series(rng.normal(0.0004, 0.01, n), index=idx)
    true_beta, true_alpha_daily = 1.3, 0.0002
    noise = pd.Series(rng.normal(0, 0.003, n), index=idx)
    # construct strategy in excess space, then add rf back so the function recovers it
    rf = at._rf_per_period(0.02)
    strat = rf + true_alpha_daily + true_beta * (bench - rf) + noise
    res = at.factor_regression(strat, bench, risk_free_annual=0.02)
    assert res.beta == pytest.approx(true_beta, abs=0.03)
    assert res.alpha_daily == pytest.approx(true_alpha_daily, abs=1.5e-4)
    assert res.alpha_annual == pytest.approx(true_alpha_daily * 252, abs=0.04)
    assert 0.0 <= res.r_squared <= 1.0
    assert res.n == n


def test_ols_zero_beta_for_independent_series():
    rng = np.random.default_rng(5)
    n = 800
    idx = pd.bdate_range("2019-01-01", periods=n)
    bench = pd.Series(rng.normal(0, 0.01, n), index=idx)
    strat = pd.Series(rng.normal(0.0003, 0.008, n), index=idx)  # independent
    res = at.factor_regression(strat, bench)
    assert abs(res.beta) < 0.15
    assert abs(res.r_squared) < 0.05


def test_rolling_factor_tracks_regime():
    """A series that is market-neutral then 2x-levered should show beta rise."""
    rng = np.random.default_rng(7)
    n = 600
    idx = pd.bdate_range("2020-01-01", periods=n)
    bench = pd.Series(rng.normal(0.0003, 0.012, n), index=idx)
    strat = bench.copy()
    strat.iloc[:300] = 0.0 * bench.iloc[:300] + rng.normal(0, 0.002, 300)  # beta ~0
    strat.iloc[300:] = 2.0 * bench.iloc[300:]                              # beta ~2
    roll = at.rolling_factor(strat, bench, window=60)
    early = roll["beta"].iloc[100:250].mean()
    late = roll["beta"].iloc[400:550].mean()
    assert early < 0.5
    assert late > 1.5


def test_quadrant_classification():
    assert at.classify_quadrant(0.10, 0.1) == "premium"      # high alpha, low beta
    assert at.classify_quadrant(0.10, 1.2) == "leveraged"
    assert at.classify_quadrant(-0.05, 0.2) == "defensive"
    assert at.classify_quadrant(-0.05, 1.0) == "closet_beta"
